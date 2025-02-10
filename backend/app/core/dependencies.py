from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.database import get_async_session
from app.core.security import (
    verify_token,
    get_user_by_id,
    InvalidTokenError,
    ExpiredTokenError,
)
from app.db.models import User

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_async_session),
) -> User:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = verify_token(token, token_type="access")
        user_id_claim = payload.get("sub")
        user_id: int = int(user_id_claim) if user_id_claim is not None else None

        if user_id is None:
            raise credentials_exception

    except (InvalidTokenError, ExpiredTokenError):
        raise credentials_exception

    user = await get_user_by_id(db, user_id=user_id)
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: AsyncSession = Depends(get_async_session),
) -> Optional[User]:
    """Get current user if token is provided and valid, otherwise None."""
    if not credentials:
        return None

    try:
        token = credentials.credentials
        payload = verify_token(token, token_type="access")
        user_id_claim = payload.get("sub")
        user_id: int = int(user_id_claim) if user_id_claim is not None else None

        if user_id is None:
            return None

        user = await get_user_by_id(db, user_id=user_id)
        if user is None or not user.is_active:
            return None

        return user

    except (InvalidTokenError, ExpiredTokenError):
        return None


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )
    return current_user
