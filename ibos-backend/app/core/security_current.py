from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.deps import get_db
from app.core.security import TokenValidationError, decode_token
from app.models.user import User
from app.models.business import Business

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_token(token, expected_type="access")
    except TokenValidationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user_id = payload.get("sub")

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def get_current_business(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Business:
    biz = db.execute(select(Business).where(Business.owner_user_id == user.id)).scalar_one_or_none()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
    return biz
