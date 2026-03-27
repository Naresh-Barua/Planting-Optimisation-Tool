from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from src.database import Base


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    token_hash = Column(String, nullable=False, index=True)

    token_type = Column(String, nullable=False)
    # "email_verification" or "password_reset"

    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User")
