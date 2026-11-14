import hashlib
import hmac
import os
import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from . import models
from .db import get_db


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    salt, _ = stored.split("$", 1)
    return hmac.compare_digest(hash_password(password, salt), stored)


def issue_token(db: Session, user: "models.User") -> str:
    token = secrets.token_urlsafe(24)
    db.add(models.Token(token=token, user_id=user.id))
    db.commit()
    return token


def current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> "models.User":
    token = authorization.removeprefix("Bearer ").strip()
    row = db.query(models.Token).filter_by(token=token).first() if token else None
    if row is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    return db.get(models.User, row.user_id)


def require_roles(*roles: str):
    def checker(user: "models.User" = Depends(current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail=f"Needs one of: {', '.join(roles)}")
        return user

    return checker


def bootstrap_admin(db: Session) -> None:
    """Create a first admin from env vars if the table is empty (used by docker compose)."""
    if db.query(models.User).count() == 0:
        email = os.getenv("ADMIN_EMAIL", "admin@example.com")
        password = os.getenv("ADMIN_PASSWORD", "change-me")
        db.add(models.User(name="Admin", email=email, password_hash=hash_password(password), role="Admin"))
        db.commit()
