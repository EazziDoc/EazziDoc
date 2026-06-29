import asyncio
import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.limiter import limiter
from app.core.metrics import registrations_total
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.doctor import Doctor
from app.models.password_reset_token import PasswordResetToken
from app.models.patient import Patient
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import (
    AdminRegisterRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from app.services import email as email_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86_400  # seconds


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=raw_token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
        path="/api/v1/auth",
    )


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    try:
        await db.flush()  # get user.id before creating profile
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    if body.role == "patient":
        db.add(Patient(user_id=user.id, first_name=body.first_name, last_name=body.last_name))
    else:
        db.add(
            Doctor(
                user_id=user.id,
                first_name=body.first_name,
                last_name=body.last_name,
                specialty=body.specialty,
                license_number=body.license_number,
                qualifications=body.qualifications,
                other_qualifications=body.other_qualifications,
                registration_status="pending_review",
            )
        )

    await db.commit()
    registrations_total.labels(role=body.role).inc()

    try:
        asyncio.get_event_loop().run_in_executor(
            None,
            lambda: email_svc.send_welcome(
                email=body.email,
                name=body.first_name,
                role=body.role,
            ),
        )
    except Exception:
        logger.exception("Welcome email failed for %s", body.email)

    return RegisterResponse(user_id=str(user.id), email=user.email, role=user.role)


@router.post(
    "/admin/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
async def register_admin(
    request: Request,
    body: AdminRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    if not settings.ADMIN_INVITE_CODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin registration is disabled on this server",
        )
    if body.invite_code != settings.ADMIN_INVITE_CODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid invite code",
        )

    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        role="admin",
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    registrations_total.labels(role="admin").inc()

    logger.info("New admin account created: %s", body.email)

    try:
        asyncio.get_event_loop().run_in_executor(
            None,
            lambda: email_svc.send_admin_welcome(
                email=body.email,
                name=body.first_name,
            ),
        )
    except Exception:
        logger.exception("Admin welcome email failed for %s", body.email)

    return RegisterResponse(user_id=str(user.id), email=user.email, role=user.role)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request, body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

    access_token = create_access_token(str(user.id), user.role)
    raw_refresh, token_hash, expires_at = create_refresh_token()

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_at=datetime.now(UTC),
        )
    )
    await db.commit()

    _set_refresh_cookie(response, raw_refresh)
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    token_hash = hash_token(refresh_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    stored = result.scalar_one_or_none()

    if not stored or stored.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired"
        )

    user_result = await db.execute(select(User).where(User.id == stored.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Rotate: delete old, issue new
    await db.delete(stored)
    access_token = create_access_token(str(user.id), user.role)
    raw_refresh, new_hash, expires_at = create_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=new_hash,
            expires_at=expires_at,
            created_at=datetime.now(UTC),
        )
    )
    await db.commit()

    _set_refresh_cookie(response, raw_refresh)
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
):
    if refresh_token:
        token_hash = hash_token(refresh_token)
        result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        stored = result.scalar_one_or_none()
        if stored:
            await db.delete(stored)
            await db.commit()

    response.delete_cookie(key=REFRESH_COOKIE, path="/api/v1/auth")


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Request a password reset link.

    Always returns 204 — we never reveal whether the email exists.
    """
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        return  # silent no-op — don't leak account existence

    # Invalidate any existing unused tokens for this user
    existing = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used.is_(False),
        )
    )
    for tok in existing.scalars().all():
        await db.delete(tok)

    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )
    await db.commit()

    # Resolve display name for the email
    first_name = user.email.split("@")[0]
    if user.role == "patient":
        profile_result = await db.execute(select(Patient).where(Patient.user_id == user.id))
        profile = profile_result.scalar_one_or_none()
        if profile:
            first_name = profile.first_name
    elif user.role == "doctor":
        profile_result = await db.execute(select(Doctor).where(Doctor.user_id == user.id))
        profile = profile_result.scalar_one_or_none()
        if profile:
            first_name = profile.first_name

    try:
        asyncio.get_event_loop().run_in_executor(
            None,
            lambda: email_svc.send_password_reset(
                email=user.email,
                name=first_name,
                token=raw_token,
            ),
        )
    except Exception:
        logger.exception("Password reset email failed for %s", user.email)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Consume a reset token and update the user's password."""
    token_hash = hash_token(body.token)
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    stored = result.scalar_one_or_none()

    if not stored or stored.used or stored.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link. Please request a new one.",
        )

    user_result = await db.execute(select(User).where(User.id == stored.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account not found")

    user.password_hash = hash_password(body.password)
    stored.used = True
    await db.commit()
    logger.info("Password reset completed for user %s", user.id)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    first_name = last_name = None
    if current_user.role == "patient":
        result = await db.execute(select(Patient).where(Patient.user_id == current_user.id))
        profile = result.scalar_one_or_none()
        if profile:
            first_name, last_name = profile.first_name, profile.last_name
    elif current_user.role == "doctor":
        result = await db.execute(select(Doctor).where(Doctor.user_id == current_user.id))
        profile = result.scalar_one_or_none()
        if profile:
            first_name, last_name = profile.first_name, profile.last_name
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        is_verified=current_user.is_verified,
        is_active=current_user.is_active,
        first_name=first_name,
        last_name=last_name,
    )
