import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    Double,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ReconstructionJob(Base):
    __tablename__ = "reconstruction_jobs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    input_file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    input_format: Mapped[str] = mapped_column(String(8), nullable=False)
    input_shape: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_dicom_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    output_orthanc_instance_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    psnr_db: Mapped[float | None] = mapped_column(Double, nullable=True)
    ssim: Mapped[float | None] = mapped_column(Double, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("idx_recon_created_at", created_at.desc()),
        Index("idx_recon_status", status),
    )
