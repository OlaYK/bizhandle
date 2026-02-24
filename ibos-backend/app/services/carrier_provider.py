import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


@dataclass(frozen=True)
class ShippingQuoteRequest:
    business_id: str
    destination_country: str
    destination_state: str | None
    destination_city: str | None
    destination_postal_code: str | None
    total_weight_kg: float
    currency: str
    options: list[dict[str, object]]


@dataclass(frozen=True)
class ShippingQuoteOption:
    provider: str
    service_code: str
    service_name: str
    amount: float
    currency: str
    eta_min_days: int
    eta_max_days: int
    zone_name: str | None = None


@dataclass(frozen=True)
class ShippingLabelRequest:
    business_id: str
    order_id: str
    provider: str
    service_code: str
    service_name: str
    recipient_name: str
    address_line1: str
    city: str
    state: str | None
    country: str
    postal_code: str | None


@dataclass(frozen=True)
class ShippingLabelResult:
    provider: str
    tracking_number: str
    label_url: str


@dataclass(frozen=True)
class ShipmentTrackingEventData:
    status: str
    description: str
    event_time: datetime


@dataclass(frozen=True)
class ShipmentTrackingResult:
    provider: str
    tracking_number: str
    events: list[ShipmentTrackingEventData]


class CarrierProvider(Protocol):
    name: str

    def quote_rates(self, request: ShippingQuoteRequest) -> list[ShippingQuoteOption]:
        ...

    def buy_label(self, request: ShippingLabelRequest) -> ShippingLabelResult:
        ...

    def track(self, *, tracking_number: str) -> ShipmentTrackingResult:
        ...


class StubCarrierProvider:
    name = "stub_carrier"

    def quote_rates(self, request: ShippingQuoteRequest) -> list[ShippingQuoteOption]:
        options: list[ShippingQuoteOption] = []
        for item in request.options:
            options.append(
                ShippingQuoteOption(
                    provider=str(item["provider"]),
                    service_code=str(item["service_code"]),
                    service_name=str(item["service_name"]),
                    amount=float(item["amount"]),
                    currency=request.currency,
                    eta_min_days=int(item["eta_min_days"]),
                    eta_max_days=int(item["eta_max_days"]),
                    zone_name=str(item["zone_name"]) if item.get("zone_name") else None,
                )
            )
        return options

    def buy_label(self, request: ShippingLabelRequest) -> ShippingLabelResult:
        tracking_number = f"SC-{uuid.uuid4().hex[:12].upper()}"
        label_url = f"https://labels.stubcarrier.local/{tracking_number}.pdf"
        return ShippingLabelResult(
            provider=self.name,
            tracking_number=tracking_number,
            label_url=label_url,
        )

    def track(self, *, tracking_number: str) -> ShipmentTrackingResult:
        return ShipmentTrackingResult(
            provider=self.name,
            tracking_number=tracking_number,
            events=[
                ShipmentTrackingEventData(
                    status="in_transit",
                    description="Shipment in transit",
                    event_time=datetime.now(timezone.utc),
                )
            ],
        )


_CARRIER_PROVIDERS: dict[str, CarrierProvider] = {
    "stub_carrier": StubCarrierProvider(),
}


def get_carrier_provider(name: str) -> CarrierProvider:
    normalized = (name or "").strip().lower()
    provider = _CARRIER_PROVIDERS.get(normalized)
    if not provider:
        available = ", ".join(sorted(_CARRIER_PROVIDERS))
        raise ValueError(f"Unknown carrier provider '{name}'. Available: {available}")
    return provider
