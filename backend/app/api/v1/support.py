"""Support / contact-form endpoint.

Authenticated users (patients and doctors) can submit a support request.
The message is forwarded to SUPPORT_EMAIL (or SMTP_USER as fallback) via email.
Admins are excluded — they have direct server access.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.limiter import limiter
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.services import email as email_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/support", tags=["support"])

_SUBJECT_MAX = 120
_MESSAGE_MAX = 2000

_ALLOWED_SUBJECTS = [
    "Report a bug or error",
    "Account issue",
    "Billing question",
    "Diagnosis / report question",
    "General enquiry",
    "Other",
]


class ContactRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=_SUBJECT_MAX)
    message: str = Field(min_length=10, max_length=_MESSAGE_MAX)


class ContactResponse(BaseModel):
    sent: bool
    message: str


@router.post("/contact", response_model=ContactResponse)
@limiter.limit("5/minute")
async def contact_support(
    request: Request,
    body: ContactRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactResponse:
    """Submit a support or error-report message.

    The authenticated user's name and email are pulled from their profile
    so the support team can reply directly.
    """
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

    display_name = " ".join(filter(None, [first_name, last_name])) or current_user.email

    try:
        asyncio.get_event_loop().run_in_executor(
            None,
            lambda: email_svc.send_support_request(
                from_name=display_name,
                from_email=current_user.email,
                from_role=current_user.role,
                subject=body.subject,
                message=body.message,
            ),
        )
    except Exception:
        logger.exception("Support email dispatch failed for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send your message. Please try again later.",
        )

    logger.info(
        "Support request submitted — user=%s role=%s subject=%r",
        current_user.id,
        current_user.role,
        body.subject,
    )
    return ContactResponse(
        sent=True,
        message="Your message has been sent. We'll get back to you as soon as possible.",
    )
