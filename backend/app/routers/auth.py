from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.rate_limit import rate_limit
from app.core.security import (create_access_token, hash_password, hash_refresh_token,
                               new_refresh_token, verify_password)
from app.db.session import get_db
from app.models.core import AuditLog, RefreshToken, User
from app.schemas.auth import LoginIn, ProfileUpdate, RegisterIn, TokenOut, UserOut
from app.services.categories import seed_default_categories

router = APIRouter(prefix="/auth", tags=["auth"])
COOKIE = "refresh_token"
# Verified against when the email is unknown, so login timing doesn't reveal which emails exist.
_DUMMY_HASH = hash_password("not-a-real-password")


def _issue(db: Session, user: User, response: Response) -> TokenOut:
    s = get_settings()
    raw, digest = new_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=digest,
                        expires_at=datetime.now(timezone.utc) + timedelta(days=s.refresh_token_days)))
    response.set_cookie(COOKIE, raw, max_age=s.refresh_token_days * 86400, httponly=True,
                        secure=s.cookie_secure, samesite="lax", path="/api/auth")
    return TokenOut(access_token=create_access_token(user.id))


@router.post("/register", response_model=TokenOut, status_code=201,
             dependencies=[Depends(rate_limit("register", 10, 3600))])
def register(body: RegisterIn, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists.")
    user = User(email=email, password_hash=hash_password(body.password), name=body.name)
    db.add(user)
    db.flush()
    seed_default_categories(db, user.id)
    db.add(AuditLog(user_id=user.id, action="register"))
    token = _issue(db, user, response)
    db.commit()
    return token


@router.post("/login", response_model=TokenOut, dependencies=[Depends(rate_limit("login", 10, 300))])
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok:
        db.add(AuditLog(user_id=user.id if user else None, action="login_failed"))
        db.commit()
        raise HTTPException(401, "Incorrect email or password.")
    if user.is_demo and not get_settings().enable_demo:
        raise HTTPException(403, "Demo mode is not enabled on this server.")
    db.add(AuditLog(user_id=user.id, action="login"))
    token = _issue(db, user, response)
    db.commit()
    return token


@router.post("/refresh", response_model=TokenOut, dependencies=[Depends(rate_limit("refresh", 30, 300))])
def refresh(response: Response, refresh_token: str | None = Cookie(default=None, alias=COOKIE),
            db: Session = Depends(get_db)):
    if not refresh_token:
        raise HTTPException(401, "Please sign in to continue.")
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token)))
    now = datetime.now(timezone.utc)
    if row is None:
        raise HTTPException(401, "Your session expired. Please sign in again.")
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if row.revoked or expires < now:
        # Reuse of a revoked token suggests theft: revoke the user's whole token family.
        if row.revoked:
            for t in db.scalars(select(RefreshToken).where(RefreshToken.user_id == row.user_id)):
                t.revoked = True
            db.add(AuditLog(user_id=row.user_id, action="refresh_token_reuse_detected"))
            db.commit()
        raise HTTPException(401, "Your session expired. Please sign in again.")
    row.revoked = True  # rotate
    user = db.get(User, row.user_id)
    if user.is_demo and not get_settings().enable_demo:
        raise HTTPException(401, "Your session expired. Please sign in again.")
    token = _issue(db, user, response)
    db.commit()
    return token


@router.post("/logout", status_code=204)
def logout(response: Response, refresh_token: str | None = Cookie(default=None, alias=COOKIE),
           db: Session = Depends(get_db)):
    if refresh_token:
        row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token)))
        if row:
            row.revoked = True
            db.commit()
    response.delete_cookie(COOKIE, path="/api/auth")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut, summary="Update display name and/or timezone")
def update_me(body: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.name is not None:
        user.name = body.name
    if body.timezone is not None:
        user.timezone = body.timezone
    db.add(AuditLog(user_id=user.id, action="profile_update", detail=",".join(sorted(body.model_fields_set))[:200]))
    db.commit()
    return user
