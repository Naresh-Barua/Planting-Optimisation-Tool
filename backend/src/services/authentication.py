"""Authentication Service

Pure service functions for user authentication and audit logging.
No FastAPI dependencies — these functions are called by routers or other services.
"""

from typing import Optional
import jwt
import bcrypt
import secrets
import hashlib
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.audit_log import AuditLog
from src.models.user import User
from src.utils.security import verify_password
from src.models.auth_token import AuthToken
from src.schemas.user import TokenData, UserRead, Role
from datetime import datetime, timedelta, timezone


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    """Authenticates a user by verifying email and password.

    Args:
        db: Async database session
        email: User's email address
        password: Plain text password to verify

    Returns:
        User object if authentication succeeds, None otherwise
    """
    email = email.strip().lower()
    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user

    if not user.is_verified:
        return None
    return user

async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db_session)
) -> User:
    """
    FastAPI dependency to extract and validate the current user from a JWT token.

    Args:
        token: JWT token extracted from the Authorization header by oauth2_scheme
        db: Async database session

    Returns:
        User: The authenticated user object from the database

    Raises:
        HTTPException: 401 Unauthorized if token is invalid, expired, or user not found

    Note:
        This dependency is used in route handlers to ensure the request is authenticated.
        It decodes the JWT, extracts the user ID from the 'sub' claim, and retrieves
        the user from the database.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decode and validate the JWT token
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(id=user_id)
    except jwt.PyJWTError:
        # Token is invalid, expired, or malformed
        raise credentials_exception

    # Retrieve user from database
    result = await db.execute(select(User).filter(User.id == token_data.id))
    user = result.scalar_one_or_none()

    if user is None:
        # User ID in token doesn't exist in database (user was deleted?)
        raise credentials_exception
    return user


# Role hierarchy mapping: defines permission levels for each role
# Higher numbers indicate greater permissions
# This enables hierarchical access control where higher-level roles
# automatically have all permissions of lower-level roles
#
# Hierarchy explanation:
# - OFFICER (1): Entry-level user with basic permissions
# - SUPERVISOR (2): Can view/manage users and has all officer permissions
# - ADMIN (3): Full system access, can perform all operations
role_hierarchy = {
    "officer": 1,
    "supervisor": 2,
    "admin": 3,
}


def require_role(required_role: Role):
    """
    FastAPI dependency factory for role-based access control.

    This function creates a dependency that checks if the authenticated user
    has sufficient permissions (role level) to access a protected endpoint.

    Args:
        required_role: The minimum role required to access the endpoint

    Returns:
        A dependency function that performs the role check

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role(Role.ADMIN))):
            # Only admins can access this endpoint
            pass

        @router.get("/supervisor-and-above")
        async def supervisor_endpoint(user: User = Depends(require_role(Role.SUPERVISOR))):
            # Supervisors and admins can access this endpoint
            pass

    Note:
        Uses hierarchical role checking: users with higher roles automatically
        have permissions of lower roles (e.g., admin can access supervisor endpoints).

    Raises:
        HTTPException: 403 Forbidden if user's role level is below required level
    """

    def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        """
        Inner function that performs the actual role validation.

        Args:
            current_user: The authenticated user (injected by get_current_user dependency)

        Returns:
            User: The current user if they have sufficient permissions

        Raises:
            HTTPException: 403 Forbidden if permissions are insufficient
        """
        # Get numeric permission levels from hierarchy
        user_role_level = role_hierarchy.get(current_user.role, 0)
        required_role_level = role_hierarchy.get(required_role.value, 0)

        # Check if user's role level meets or exceeds the requirement
        if user_role_level < required_role_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The user does not have adequate permissions.",
            )
        return current_user

    return role_checker


async def require_role_async(required_role: Role):
    """
    Async version of require_role for compatibility with async dependencies.

    This function provides the same role-based access control as require_role
    but works with the async get_current_active_user dependency.

    Args:
        required_role: The minimum role required to access the endpoint

    Returns:
        An async dependency function that performs the role check

    Note:
        This is used when you need to work with UserRead schemas instead of
        User models, typically in routes that need the async dependency chain.

    Raises:
        HTTPException: 403 Forbidden if user's role level is below required level
    """

    async def role_checker(
        current_user: UserRead = Depends(get_current_active_user),
    ) -> UserRead:
        """
        Inner async function that performs the role validation.

        Args:
            current_user: The authenticated user as UserRead schema

        Returns:
            UserRead: The current user if they have sufficient permissions

        Raises:
            HTTPException: 403 Forbidden if permissions are insufficient
        """
        # Get numeric permission levels from hierarchy
        user_role_level = role_hierarchy.get(current_user.role, 0)
        required_role_level = role_hierarchy.get(required_role.value, 0)

        # Check if user's role level meets or exceeds the requirement
        if user_role_level < required_role_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The user does not have adequate permissions.",
            )
        return current_user

    return role_checker



async def log_audit_event(
    db: AsyncSession,
    user_id: int,
    event_type: str,
    details: str,
):
    """Records a security audit event to the database.

    Args:
        db: Async database session
        user_id: ID of the user who triggered the event
        event_type: Type of event (e.g., "user_create", "login", "role_change")
        details: Detailed description of the event
    """
    db_log = AuditLog(user_id=user_id, event_type=event_type, details=details)
    db.add(db_log)
    await db.commit()


# =========================
# TOKEN HELPERS
# =========================

def generate_raw_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_auth_token(
    db,
    user_id: int,
    token_type: str,
    expires_minutes: int = 10,
):
    raw_token = generate_raw_token()
    token_hash = hash_token(raw_token)

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)

    db_token = AuthToken(
        user_id=user_id,
        token_hash=token_hash,
        token_type=token_type,
        expires_at=expires_at,
    )

    db.add(db_token)
    await db.commit()
    await db.refresh(db_token)

    return raw_token


async def get_valid_token(db, token: str, token_type: str):
    token_hash = hash_token(token)

    result = await db.execute(
        select(AuthToken).where(
            AuthToken.token_hash == token_hash,
            AuthToken.token_type == token_type,
            AuthToken.used_at.is_(None),
            AuthToken.expires_at > datetime.now(timezone.utc),
        )
    )
    return result.scalar_one_or_none()


async def mark_token_used(db, token_obj: AuthToken):
    token_obj.used_at = datetime.now(timezone.utc)
    

async def invalidate_user_tokens(db, user_id: int, token_type: str):
    result = await db.execute(
        select(AuthToken).where(
            AuthToken.user_id == user_id,
            AuthToken.token_type == token_type,
            AuthToken.used_at.is_(None),
        )
    )
    tokens = result.scalars().all()

    now = datetime.now(timezone.utc)
    for token in tokens:
        token.used_at = now

    