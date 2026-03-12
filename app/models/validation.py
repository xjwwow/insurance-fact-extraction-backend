from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class ValidationRule(TimestampMixin, Base):
    __tablename__ = "validation_rules"

    rule_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rule_code: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    rule_name: Mapped[str] = mapped_column(String(256), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    tolerance: Mapped[float | None] = mapped_column(Numeric(18, 8))
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    applicable_metric_ids: Mapped[dict | None] = mapped_column(JSONB)
    applicable_company_ids: Mapped[dict | None] = mapped_column(JSONB)
    applicable_scope: Mapped[dict | None] = mapped_column(JSONB)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ReviewLog(Base):
    __tablename__ = "review_logs"

    review_log_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    fact_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("facts.fact_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    old_value_json: Mapped[dict | None] = mapped_column(JSONB)
    new_value_json: Mapped[dict | None] = mapped_column(JSONB)
    reviewer: Mapped[str] = mapped_column(String(128), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    fact = relationship("Fact", back_populates="review_logs")
