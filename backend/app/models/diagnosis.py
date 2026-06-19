import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewing_doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True
    )

    # Image object keys in Cloudflare R2 (1-5 views per diagnosis)
    image_keys: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    gradcam_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Modality: chest_xray | fundus | skin | brain_mri | mammography
    modality: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # AI inference
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_predictions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Structured report from LLM (see DiagnosisReport schema)
    report: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Status lifecycle
    # pending → ai_complete → under_review → confirmed | overridden | flagged
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)

    doctor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    doctor_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    patient: Mapped["Patient"] = relationship(back_populates="diagnoses")
    reviewing_doctor: Mapped["Doctor"] = relationship(back_populates="reviews")
    appointment: Mapped["Appointment"] = relationship(back_populates="diagnosis", uselist=False)
