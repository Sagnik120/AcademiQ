from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.models.user import User, UserRole
from app.schemas.auth import RegisterRequest, LoginRequest
from app.utils.password import hash_password, verify_password
from app.utils.jwt import create_access_token, create_refresh_token, decode_token
import secrets

async def register_user(data: RegisterRequest, db: AsyncSession):
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == data.email))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    verification_token = secrets.token_urlsafe(32)

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        role=UserRole(data.role.value),
        first_name=data.first_name,
        last_name=data.last_name,
        email_verification_token=verification_token
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # TODO: Send verification email via Resend when configured
    print(f"[DEV] Verification token for {user.email}: {verification_token}")

    return user

async def login_user(data: LoginRequest, db: AsyncSession):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive or deleted"
        )

    token_data = {"sub": str(user.id), "role": user.role.value, "email": user.email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return user, access_token, refresh_token

async def refresh_tokens(refresh_token: str):
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    token_data = {"sub": payload["sub"], "role": payload["role"], "email": payload["email"]}
    new_access = create_access_token(token_data)
    new_refresh = create_refresh_token(token_data)
    return new_access, new_refresh
