from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.auth import (
    RegisterRequest, LoginRequest, AuthResponse,
    TokenResponse, RefreshRequest, MessageResponse, UserResponse
)
from app.services.auth_service import register_user, login_user, refresh_tokens
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = await register_user(data, db)
    token_data = {"sub": str(user.id), "role": user.role.value, "email": user.email}
    from app.utils.jwt import create_access_token, create_refresh_token
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    return AuthResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role.value,
            is_email_verified=user.is_email_verified,
            avatar_url=user.avatar_url
        ),
        tokens=TokenResponse(access_token=access_token, refresh_token=refresh_token)
    )

@router.post("/login", response_model=AuthResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user, access_token, refresh_token = await login_user(data, db)
    return AuthResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role.value,
            is_email_verified=user.is_email_verified,
            avatar_url=user.avatar_url
        ),
        tokens=TokenResponse(access_token=access_token, refresh_token=refresh_token)
    )

@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest):
    access_token, new_refresh = await refresh_tokens(data.refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=new_refresh)

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        role=current_user.role.value,
        is_email_verified=current_user.is_email_verified,
        avatar_url=current_user.avatar_url
    )

@router.post("/logout", response_model=MessageResponse)
async def logout(current_user: User = Depends(get_current_user)):
    # With stateless JWT, logout is handled client-side
    # Redis token blacklist can be added later
    return MessageResponse(message="Logged out successfully")
