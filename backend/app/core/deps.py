import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.core import User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(401, "Please sign in to continue.")
    try:
        user_id = decode_access_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Your session expired. Please sign in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid session. Please sign in again.")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(401, "Account not found.")
    return user
