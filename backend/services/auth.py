"""
services/auth.py — FastAPI authentication dependency for Iroko AI.

Provides ``get_current_user`` which decodes the JWT Bearer token, looks up
the user in the database, and returns the ``User`` ORM instance.  Raises
HTTP 401 if the token is missing, invalid, or the user doesn't exist.

This module uses the **synchronous** database session (``models.database``)
to stay compatible with the existing route layer.  For async routes, use
the async variant in ``services/database.py``.
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from core.config import settings
from models.database import get_db, User

# ── OAuth2 scheme ─────────────────────────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Dependency ────────────────────────────────────────────────────────────────

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency that extracts and validates the current user from a
    Bearer JWT token.

    Parameters
    ----------
    token : str
        Bearer token extracted by ``OAuth2PasswordBearer``.
    db : Session
        Database session from ``get_db``.

    Returns
    -------
    User
        The authenticated, active user.

    Raises
    ------
    HTTPException (401)
        If the token is invalid/expired or the user is not found/inactive.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        from jose import jwt
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = (
        db.query(User)
        .filter(User.id == user_id, User.is_active == True)
        .first()
    )

    if user is None:
        raise credentials_exception

    return user
