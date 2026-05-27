from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class StorageObject(Base):
    __tablename__ = "storage_objects"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    bucket: Mapped[str] = mapped_column(String(64), nullable=False)
    object_key: Mapped[str] = mapped_column(String(256), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint("bucket", "object_key", name="uq_storage_bucket_key"),
        Index("idx_storage_sha256", "sha256"),
        Index("idx_storage_source", "source"),
        Index("idx_storage_created_at", "created_at"),
    )
