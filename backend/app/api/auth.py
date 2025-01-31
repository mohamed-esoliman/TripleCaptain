from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from app.db.database import get_async_session
from app.db.models import User
from app.core.security import (
    authenticate_user,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_refresh_token_record,
    create_refresh_token_record,
    revoke_refresh_token,
    revoke_all_user_tokens,
    InvalidTokenError,
    ExpiredTokenError,
)
from app.core.dependencies import get_current_user
from app.core.config import settings
from app.api.schemas import (
    UserRegister,
    UserLogin,
    UserResponse,
    Token,
    RefreshTokenRequest,
    UserUpdate,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserRegister, db: AsyncSession = Depends(get_async_session)
):
    """Register a new user."""
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken"
        )

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        fpl_team_id=user_data.fpl_team_id,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


@router.post("/login", response_model=Token)
async def login(
    user_credentials: UserLogin, db: AsyncSession = Depends(get_async_session)
):
    """Login and get access token."""
    user = await authenticate_user(
        db, user_credentials.email, user_credentials.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )

    # Create tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )

    refresh_token = create_refresh_token(
        data={"sub": str(user.id)}, expires_delta=refresh_token_expires
    )

    # Store refresh token in database
    await create_refresh_token_record(
        db=db,
        user_id=user.id,
        token=refresh_token,
        expires_at=datetime.utcnow() + refresh_token_expires,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_request: RefreshTokenRequest, db: AsyncSession = Depends(get_async_session)
):
    """Refresh access token using refresh token."""
    try:
        # Verify refresh token
        payload = verify_token(token_request.refresh_token, token_type="refresh")
        user_id = int(payload.get("sub"))

    except (InvalidTokenError, ExpiredTokenError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    # Check if refresh token exists in database and is not revoked
    refresh_token_record = await get_refresh_token_record(
        db, token_request.refresh_token
    )
    if not refresh_token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    user = refresh_token_record.user
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )

    # Create new tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    new_access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )

    new_refresh_token = create_refresh_token(
        data={"sub": str(user.id)}, expires_delta=refresh_token_expires
    )

    # Revoke old refresh token and create new one
    await revoke_refresh_token(db, token_request.refresh_token)
    await create_refresh_token_record(
        db=db,
        user_id=user.id,
        token=new_refresh_token,
        expires_at=datetime.utcnow() + refresh_token_expires,
    )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(
    token_request: RefreshTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Logout and revoke refresh token."""
    await revoke_refresh_token(db, token_request.refresh_token)
    return {"message": "Successfully logged out"}


@router.post("/logout-all")
async def logout_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Logout from all devices by revoking all refresh tokens."""
    count = await revoke_all_user_tokens(db, current_user.id)
    return {"message": f"Successfully logged out from {count} devices"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Update current user information (e.g., username, fpl_team_id)."""
    changed = False

    if payload.username is not None and payload.username != current_user.username:
        # Check for username uniqueness
        result = await db.execute(select(User).where(User.username == payload.username))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )
        current_user.username = payload.username
        changed = True

    if (
        payload.fpl_team_id is not None
        and payload.fpl_team_id != current_user.fpl_team_id
    ):
        current_user.fpl_team_id = payload.fpl_team_id
        changed = True

    if changed:
        await db.commit()
        await db.refresh(current_user)

    return current_user
