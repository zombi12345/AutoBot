from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class SubscriptionStatus:
    ACTIVE = "active"
    PAUSED = "paused"


class SearchSubscription(Base):
    __tablename__ = "search_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="avby")
    brand: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    year_from: Mapped[int | None] = mapped_column(nullable=True)
    year_to: Mapped[int | None] = mapped_column(nullable=True)
    price_from: Mapped[int | None] = mapped_column(nullable=True)
    price_to: Mapped[int | None] = mapped_column(nullable=True)
    fuel_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    transmission: Mapped[str | None] = mapped_column(String(32), nullable=True)
    body_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mileage_to: Mapped[int | None] = mapped_column(nullable=True)
    engine_cc_from: Mapped[int | None] = mapped_column(nullable=True)
    engine_cc_to: Mapped[int | None] = mapped_column(nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=SubscriptionStatus.ACTIVE)
    seen_listing_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="subscriptions")