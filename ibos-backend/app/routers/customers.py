import csv
import re
import uuid
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.permissions import require_business_roles
from app.core.security_current import BusinessAccess, get_current_user
from app.models.customer import Customer, CustomerTag, CustomerTagLink
from app.models.user import User
from app.schemas.common import PaginationMeta
from app.schemas.customer import (
    CustomerCreateIn,
    CustomerCreateOut,
    CustomerCsvImportIn,
    CustomerCsvImportOut,
    CustomerCsvImportRejectedOut,
    CustomerListOut,
    CustomerOut,
    CustomerTagCreateIn,
    CustomerTagListOut,
    CustomerTagOut,
    CustomerUpdateIn,
)
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/customers", tags=["customers"])
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _tag_out(tag: CustomerTag) -> CustomerTagOut:
    return CustomerTagOut(id=tag.id, name=tag.name, color=tag.color, created_at=tag.created_at)


def _tags_by_customer_id(
    db: Session,
    *,
    business_id: str,
    customer_ids: list[str],
) -> dict[str, list[CustomerTagOut]]:
    if not customer_ids:
        return {}

    rows = db.execute(
        select(CustomerTagLink.customer_id, CustomerTag)
        .join(CustomerTag, CustomerTag.id == CustomerTagLink.tag_id)
        .where(
            CustomerTagLink.business_id == business_id,
            CustomerTagLink.customer_id.in_(customer_ids),
        )
        .order_by(CustomerTag.name.asc())
    ).all()

    out: dict[str, list[CustomerTagOut]] = {customer_id: [] for customer_id in customer_ids}
    for customer_id, tag in rows:
        out.setdefault(customer_id, []).append(_tag_out(tag))
    return out


def _customer_out(customer: Customer, tags: list[CustomerTagOut] | None = None) -> CustomerOut:
    return CustomerOut(
        id=customer.id,
        name=customer.name,
        phone=customer.phone,
        email=customer.email,
        note=customer.note,
        tags=tags or [],
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )


def _customer_or_404(db: Session, *, business_id: str, customer_id: str) -> Customer:
    customer = db.execute(
        select(Customer).where(Customer.id == customer_id, Customer.business_id == business_id)
    ).scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


def _tag_or_404(db: Session, *, business_id: str, tag_id: str) -> CustomerTag:
    tag = db.execute(
        select(CustomerTag).where(CustomerTag.id == tag_id, CustomerTag.business_id == business_id)
    ).scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


def _load_tag_map(
    db: Session,
    *,
    business_id: str,
    tag_ids: list[str],
) -> dict[str, CustomerTag]:
    if not tag_ids:
        return {}
    unique_tag_ids = list(dict.fromkeys(tag_ids))
    rows = db.execute(
        select(CustomerTag).where(
            CustomerTag.business_id == business_id,
            CustomerTag.id.in_(unique_tag_ids),
        )
    ).scalars().all()
    tag_map = {tag.id: tag for tag in rows}
    if len(tag_map) != len(unique_tag_ids):
        raise HTTPException(status_code=404, detail="One or more tags not found")
    return tag_map


def _email_exists_for_other_customer(
    db: Session,
    *,
    business_id: str,
    email: str,
    customer_id: str | None = None,
) -> bool:
    stmt = select(Customer.id).where(
        Customer.business_id == business_id,
        func.lower(Customer.email) == email.lower(),
    )
    if customer_id:
        stmt = stmt.where(Customer.id != customer_id)
    return db.execute(stmt).scalar_one_or_none() is not None


def _normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    return cleaned or None


def _extract_row_value(row_map: dict[str, str], keys: list[str]) -> str | None:
    for key in keys:
        candidate = row_map.get(key)
        if candidate:
            return candidate
    return None


def _parse_csv_row_from_header(row: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in row.items():
        if key is None:
            continue
        normalized[key.strip().lower()] = (value or "").strip()
    return {
        "name": _extract_row_value(normalized, ["name", "customer_name", "full_name"]) or "",
        "email": _extract_row_value(normalized, ["email"]) or "",
        "phone": _extract_row_value(normalized, ["phone", "phone_number", "mobile"]) or "",
        "note": _extract_row_value(normalized, ["note", "notes"]) or "",
    }


def _parse_csv_row_without_header(raw_row: list[str]) -> dict[str, str]:
    cols = [value.strip() for value in raw_row]
    return {
        "name": cols[0] if len(cols) > 0 else "",
        "email": cols[1] if len(cols) > 1 else "",
        "phone": cols[2] if len(cols) > 2 else "",
        "note": cols[3] if len(cols) > 3 else "",
    }


@router.post(
    "/import-csv",
    response_model=CustomerCsvImportOut,
    summary="Import customers from CSV content",
    responses=error_responses(400, 401, 403, 404, 409, 422, 500),
)
def import_customers_csv(
    payload: CustomerCsvImportIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    unique_tag_ids = list(dict.fromkeys(payload.default_tag_ids))
    if unique_tag_ids:
        _load_tag_map(db, business_id=access.business.id, tag_ids=unique_tag_ids)

    existing_email_rows = db.execute(
        select(func.lower(Customer.email)).where(
            Customer.business_id == access.business.id,
            Customer.email.is_not(None),
        )
    ).all()
    seen_emails = {str(email).lower() for (email,) in existing_email_rows if email}

    imported_ids: list[str] = []
    rejected_rows: list[CustomerCsvImportRejectedOut] = []
    total_rows = 0

    stream = StringIO(payload.csv_content)
    if payload.has_header:
        reader = csv.DictReader(stream, delimiter=payload.delimiter)
        if not reader.fieldnames:
            raise HTTPException(status_code=400, detail="CSV header row is missing")
        header_lookup = {header.strip().lower() for header in reader.fieldnames if header}
        if not {"name", "customer_name", "full_name"} & header_lookup:
            raise HTTPException(
                status_code=400,
                detail="CSV header must include one of: name, customer_name, full_name",
            )
        row_iterator = enumerate(reader, start=2)
        parse_row = _parse_csv_row_from_header
    else:
        reader = csv.reader(stream, delimiter=payload.delimiter)
        row_iterator = enumerate(reader, start=1)
        parse_row = _parse_csv_row_without_header

    for row_number, raw in row_iterator:
        parsed_row = parse_row(raw)
        if not any(parsed_row.values()):
            continue
        total_rows += 1

        name = parsed_row["name"].strip()
        email = _normalize_email(parsed_row["email"])
        phone = parsed_row["phone"].strip() or None
        note = parsed_row["note"].strip() or None

        if not name:
            rejected_rows.append(
                CustomerCsvImportRejectedOut(
                    row_number=row_number,
                    reason="Missing required name",
                    row_data=parsed_row,
                )
            )
            continue

        if email and not EMAIL_RE.match(email):
            rejected_rows.append(
                CustomerCsvImportRejectedOut(
                    row_number=row_number,
                    reason="Invalid email format",
                    row_data=parsed_row,
                )
            )
            continue

        if email and email in seen_emails:
            rejected_rows.append(
                CustomerCsvImportRejectedOut(
                    row_number=row_number,
                    reason="Email already exists",
                    row_data=parsed_row,
                )
            )
            continue

        customer_id = str(uuid.uuid4())
        db.add(
            Customer(
                id=customer_id,
                business_id=access.business.id,
                name=name,
                phone=phone,
                email=email,
                note=note,
            )
        )
        db.flush()

        for tag_id in unique_tag_ids:
            db.add(
                CustomerTagLink(
                    id=str(uuid.uuid4()),
                    business_id=access.business.id,
                    customer_id=customer_id,
                    tag_id=tag_id,
                )
            )

        if email:
            seen_emails.add(email)
        imported_ids.append(customer_id)

    imported_count = len(imported_ids)
    rejected_count = len(rejected_rows)

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="customer.import_csv",
        target_type="customer",
        metadata_json={
            "total_rows": total_rows,
            "imported_count": imported_count,
            "rejected_count": rejected_count,
            "default_tag_count": len(unique_tag_ids),
        },
    )
    db.commit()

    return CustomerCsvImportOut(
        total_rows=total_rows,
        imported_count=imported_count,
        rejected_count=rejected_count,
        imported_ids=imported_ids,
        rejected_rows=rejected_rows,
    )


@router.post(
    "",
    response_model=CustomerCreateOut,
    summary="Create customer",
    responses=error_responses(400, 401, 403, 404, 409, 422, 500),
)
def create_customer(
    payload: CustomerCreateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    if payload.email and _email_exists_for_other_customer(
        db,
        business_id=access.business.id,
        email=str(payload.email),
    ):
        raise HTTPException(status_code=409, detail="Email already exists for another customer")

    customer_id = str(uuid.uuid4())
    customer = Customer(
        id=customer_id,
        business_id=access.business.id,
        name=payload.name,
        phone=payload.phone,
        email=str(payload.email) if payload.email else None,
        note=payload.note,
    )
    db.add(customer)
    db.flush()

    unique_tag_ids = list(dict.fromkeys(payload.tag_ids))
    if unique_tag_ids:
        _load_tag_map(
            db,
            business_id=access.business.id,
            tag_ids=unique_tag_ids,
        )
        for tag_id in unique_tag_ids:
            db.add(
                CustomerTagLink(
                    id=str(uuid.uuid4()),
                    business_id=access.business.id,
                    customer_id=customer_id,
                    tag_id=tag_id,
                )
            )

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="customer.create",
        target_type="customer",
        target_id=customer_id,
        metadata_json={
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "tag_count": len(unique_tag_ids),
        },
    )
    db.commit()
    return CustomerCreateOut(id=customer_id)


@router.get(
    "",
    response_model=CustomerListOut,
    summary="List customers",
    responses=error_responses(400, 401, 403, 422, 500),
)
def list_customers(
    q: str | None = Query(default=None),
    tag_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    normalized_q = q.strip().lower() if q and q.strip() else None
    normalized_tag_id = tag_id.strip() if tag_id and tag_id.strip() else None

    count_stmt = select(func.count(Customer.id)).where(Customer.business_id == access.business.id)
    data_stmt = select(Customer).where(Customer.business_id == access.business.id)

    if normalized_tag_id:
        count_stmt = count_stmt.join(
            CustomerTagLink,
            (CustomerTagLink.customer_id == Customer.id)
            & (CustomerTagLink.business_id == access.business.id)
            & (CustomerTagLink.tag_id == normalized_tag_id),
        )
        data_stmt = data_stmt.join(
            CustomerTagLink,
            (CustomerTagLink.customer_id == Customer.id)
            & (CustomerTagLink.business_id == access.business.id)
            & (CustomerTagLink.tag_id == normalized_tag_id),
        )

    if normalized_q:
        like_q = f"%{normalized_q}%"
        q_filter = or_(
            func.lower(Customer.name).like(like_q),
            func.lower(func.coalesce(Customer.email, "")).like(like_q),
            func.lower(func.coalesce(Customer.phone, "")).like(like_q),
        )
        count_stmt = count_stmt.where(q_filter)
        data_stmt = data_stmt.where(q_filter)

    total = int(db.execute(count_stmt).scalar_one())
    customers = db.execute(
        data_stmt.order_by(Customer.created_at.desc()).offset(offset).limit(limit)
    ).scalars().all()

    tags_map = _tags_by_customer_id(
        db,
        business_id=access.business.id,
        customer_ids=[customer.id for customer in customers],
    )
    items = [_customer_out(customer, tags_map.get(customer.id, [])) for customer in customers]
    count = len(items)
    return CustomerListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
        q=normalized_q,
        tag_id=normalized_tag_id,
    )


@router.patch(
    "/{customer_id}",
    response_model=CustomerOut,
    summary="Update customer",
    responses=error_responses(400, 401, 403, 404, 409, 422, 500),
)
def update_customer(
    customer_id: str,
    payload: CustomerUpdateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    customer = _customer_or_404(db, business_id=access.business.id, customer_id=customer_id)
    previous_state = {
        "name": customer.name,
        "phone": customer.phone,
        "email": customer.email,
        "note": customer.note,
    }

    fields_set = payload.model_fields_set
    if "name" in fields_set:
        if payload.name is None:
            raise HTTPException(status_code=400, detail="name cannot be null")
        customer.name = payload.name
    if "phone" in fields_set:
        customer.phone = payload.phone
    if "email" in fields_set:
        next_email = str(payload.email) if payload.email else None
        if next_email and _email_exists_for_other_customer(
            db,
            business_id=access.business.id,
            email=next_email,
            customer_id=customer.id,
        ):
            raise HTTPException(status_code=409, detail="Email already exists for another customer")
        customer.email = next_email
    if "note" in fields_set:
        customer.note = payload.note

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="customer.update",
        target_type="customer",
        target_id=customer.id,
        metadata_json={
            "previous": previous_state,
            "next": {
                "name": customer.name,
                "phone": customer.phone,
                "email": customer.email,
                "note": customer.note,
            },
        },
    )
    db.commit()
    db.refresh(customer)
    tags_map = _tags_by_customer_id(
        db,
        business_id=access.business.id,
        customer_ids=[customer.id],
    )
    return _customer_out(customer, tags_map.get(customer.id, []))


@router.delete(
    "/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete customer",
    responses=error_responses(401, 403, 404, 500),
)
def delete_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    customer = _customer_or_404(db, business_id=access.business.id, customer_id=customer_id)
    db.query(CustomerTagLink).filter(
        CustomerTagLink.business_id == access.business.id,
        CustomerTagLink.customer_id == customer.id,
    ).delete(synchronize_session=False)
    db.delete(customer)
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="customer.delete",
        target_type="customer",
        target_id=customer.id,
        metadata_json={"name": customer.name, "email": customer.email},
    )
    db.commit()
    return None


@router.post(
    "/tags",
    response_model=CustomerTagOut,
    summary="Create customer tag",
    responses=error_responses(400, 401, 403, 409, 422, 500),
)
def create_customer_tag(
    payload: CustomerTagCreateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    existing_tag = db.execute(
        select(CustomerTag.id).where(
            CustomerTag.business_id == access.business.id,
            func.lower(CustomerTag.name) == payload.name.lower(),
        )
    ).scalar_one_or_none()
    if existing_tag:
        raise HTTPException(status_code=409, detail="Tag name already exists")

    tag = CustomerTag(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        name=payload.name,
        color=payload.color,
    )
    db.add(tag)
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="customer.tag.create",
        target_type="customer_tag",
        target_id=tag.id,
        metadata_json={"name": tag.name, "color": tag.color},
    )
    db.commit()
    db.refresh(tag)
    return _tag_out(tag)


@router.get(
    "/tags",
    response_model=CustomerTagListOut,
    summary="List customer tags",
    responses=error_responses(401, 403, 500),
)
def list_customer_tags(
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    tags = db.execute(
        select(CustomerTag)
        .where(CustomerTag.business_id == access.business.id)
        .order_by(CustomerTag.name.asc())
    ).scalars().all()
    return CustomerTagListOut(items=[_tag_out(tag) for tag in tags])


@router.post(
    "/{customer_id}/tags/{tag_id}",
    response_model=CustomerOut,
    summary="Attach tag to customer",
    responses=error_responses(401, 403, 404, 409, 500),
)
def attach_customer_tag(
    customer_id: str,
    tag_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    customer = _customer_or_404(db, business_id=access.business.id, customer_id=customer_id)
    tag = _tag_or_404(db, business_id=access.business.id, tag_id=tag_id)

    existing_link = db.execute(
        select(CustomerTagLink).where(
            CustomerTagLink.business_id == access.business.id,
            CustomerTagLink.customer_id == customer.id,
            CustomerTagLink.tag_id == tag.id,
        )
    ).scalar_one_or_none()
    if existing_link:
        tags_map = _tags_by_customer_id(
            db,
            business_id=access.business.id,
            customer_ids=[customer.id],
        )
        return _customer_out(customer, tags_map.get(customer.id, []))

    db.add(
        CustomerTagLink(
            id=str(uuid.uuid4()),
            business_id=access.business.id,
            customer_id=customer.id,
            tag_id=tag.id,
        )
    )
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="customer.tag.attach",
        target_type="customer",
        target_id=customer.id,
        metadata_json={"tag_id": tag.id, "tag_name": tag.name},
    )
    db.commit()
    db.refresh(customer)
    tags_map = _tags_by_customer_id(
        db,
        business_id=access.business.id,
        customer_ids=[customer.id],
    )
    return _customer_out(customer, tags_map.get(customer.id, []))


@router.delete(
    "/{customer_id}/tags/{tag_id}",
    response_model=CustomerOut,
    summary="Detach tag from customer",
    responses=error_responses(401, 403, 404, 500),
)
def detach_customer_tag(
    customer_id: str,
    tag_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    customer = _customer_or_404(db, business_id=access.business.id, customer_id=customer_id)
    tag = _tag_or_404(db, business_id=access.business.id, tag_id=tag_id)

    existing_link = db.execute(
        select(CustomerTagLink).where(
            CustomerTagLink.business_id == access.business.id,
            CustomerTagLink.customer_id == customer.id,
            CustomerTagLink.tag_id == tag.id,
        )
    ).scalar_one_or_none()
    if existing_link:
        db.delete(existing_link)
        log_audit_event(
            db,
            business_id=access.business.id,
            actor_user_id=actor.id,
            action="customer.tag.detach",
            target_type="customer",
            target_id=customer.id,
            metadata_json={"tag_id": tag.id, "tag_name": tag.name},
        )
        db.commit()

    db.refresh(customer)
    tags_map = _tags_by_customer_id(
        db,
        business_id=access.business.id,
        customer_ids=[customer.id],
    )
    return _customer_out(customer, tags_map.get(customer.id, []))
