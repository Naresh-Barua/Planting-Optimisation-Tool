"""Authentication Router

This module provides API endpoints for user authentication and authorization:
- Token-based login (OAuth2 password flow)
- User registration
- Current user information retrieval

All endpoints use JWT tokens for stateless authentication.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db_session
from src.dependencies import create_access_token, get_current_user, require_role
from src.models import User
from src.schemas.farm import FarmRead
from src.schemas.user import Role, Token, UserCreate, UserRead
from src.services import authentication as authentication_service
from src.services import farm as farm_service
from src.services import user as user_service
from src.dependencies import create_access_token  # Use the timezone-aware version
from src.services.authentication import (
    authenticate_user,
    create_auth_token,
    get_current_user,
    get_password_hash,
    get_valid_token,
    invalidate_user_tokens,
    mark_token_used,
    require_role,
)
from src.models import User
from src.schemas.user import Role, Token, UserRead, UserCreate
from src.services.email_service import send_email
from src.config import settings

from pydantic import BaseModel

class VerifyEmailRequest(BaseModel):
    token: str

class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db_session),
):
    """OAuth2 compatible token login endpoint.

    Authenticates a user using email (as username) and password, then returns
    a JWT access token for subsequent API requests.

    Args:
        form_data: OAuth2 form containing username (email) and password
        db: Database session

    Returns:
        Token response containing access_token and token_type

    Raises:
        HTTPException: 401 if credentials are invalid

    Example:
        POST /auth/token
        Content-Type: application/x-www-form-urlencoded

        username=user@example.com&password=secretpassword

        Response:
        {
            "access_token": "eyJhbGc...",
            "token_type": "bearer"
        }
    """
    user = await authentication_service.authenticate_user(db, email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Create JWT token with user ID and role in the payload
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register")
async def register_user(user: UserCreate, db: AsyncSession = Depends(get_db_session)):
    """Register a new user account.

    Creates a new user with the provided email, name, password, and role.
    This is a public endpoint that allows self-registration.

    Args:
        user: User creation data (email, name, password, role)
        db: Database session

    Returns:
        UserRead: The created user (without password)

    Raises:
        HTTPException: 400 if email is already registered

    Note:
        - Passwords are hashed before storage using bcrypt
        - Default role is "officer" if not specified
        - The password field is never returned in the response
        - For production, you may want to restrict which roles can self-register
          or require email verification

    Example:
        POST /auth/register
        {
            "email": "newuser@example.com",
            "name": "John Doe",
            "password": "securepassword123",
            "role": "officer"
        }
    """
    

    # Hash the password before storing
    hashed_password = get_password_hash(user.password)

    # Create new user
    db_user = User(
        email=user.email,
        name=user.name,
        hashed_password=hashed_password,
        role=user.role,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    # Create verification token
    token = await create_auth_token(
    db,
    user_id=db_user.id,
    token_type="email_verification",
    expires_minutes=settings.email_verification_expiry_minutes,
    )

    # Build verification link
    verification_link = f"{settings.frontend_base_url}/verify-email?token={token}"

    # Send email
    send_email(
    subject="Verify your account",
    recipient=db_user.email,
    body=f"Click this link to verify your account:\n{verification_link}",
    )

    return {"message": "User registered. Verification email sent."}


@router.get("/users/me", response_model=UserRead)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get the currently authenticated user's information.

    Returns the profile of the user making the request based on their JWT token.

    Args:
        current_user: Authenticated user (injected from JWT token)

    Returns:
        UserRead: Current user's profile information

    Requires:
        Valid JWT token in Authorization header

    Example:
        GET /auth/users/me
        Authorization: Bearer eyJhbGc...

        Response:
        {
            "id": 1,
            "email": "user@example.com",
            "name": "John Doe",
            "role": "officer"
        }
    """
    return current_user


@router.get("/users/me/items", response_model=List[FarmRead])
async def read_own_items(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(Role.OFFICER)),
):
    """
    Example endpoint demonstrating admin-only access.

    This is a placeholder endpoint showing how to restrict access to admin users only.
    In production, replace with actual business logic.

    Args:
        current_user: Authenticated admin user

    Returns:
        List of items owned by the current admin user

    Requires:
        Valid JWT token with admin role

    Note:
        This endpoint is restricted to admins only. Officers and supervisors
        will receive a 403 Forbidden response.
    """
    return await farm_service.list_farms_by_user(db, current_user.id)


@router.post("/verify-email")
async def verify_email(
    request: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db_session),
):
    token_obj = await get_valid_token(
        db,
        token=request.token,
        token_type="email_verification",
    )

    if not token_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )

    # Get user
    result = await db.execute(select(User).filter(User.id == token_obj.user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Mark user verified
    user.is_verified = True

    # Mark token used
    await mark_token_used(db, token_obj)

    await db.commit()

    return {"message": "Email verified successfully"}


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(User).filter(User.email == request.email))
    user = result.scalar_one_or_none()

    if user:
        await invalidate_user_tokens(db, user.id, "password_reset")

        token = await create_auth_token(
            db,
            user_id=user.id,
            token_type="password_reset",
            expires_minutes=settings.password_reset_expiry_minutes,
        )

        reset_link = f"{settings.frontend_base_url}/reset-password?token={token}"

        send_email(
            subject="Reset your password",
            recipient=user.email,
            body=f"Click this link to reset your password:\n{reset_link}",
        )

    return {
        "message": "If an account with that email exists, a password reset email has been sent."
    }


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db_session),
):
    token_obj = await get_valid_token(
        db,
        token=request.token,
        token_type="password_reset",
    )

    if not token_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )

    result = await db.execute(select(User).filter(User.id == token_obj.user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.hashed_password = get_password_hash(request.new_password)

    await mark_token_used(db, token_obj)
    await db.commit()

    return {"message": "Password reset successfully"}
