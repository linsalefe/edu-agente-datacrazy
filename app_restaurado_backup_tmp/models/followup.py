from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from app.database import Base


class FollowupType(enum.Enum):
    three_hours = "3h"
    one_day = "1d"
    three_days = "3d"
    seven_days = "7d"


class FollowupStatus(enum.Enum):
    pending = "pending"
    sent = "sent"
    cancelled = "cancelled"


class Followup(Base):
    __tablename__ = "followups"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'), nullable=False)
    type = Column(SQLEnum(FollowupType), nullable=False)
    scheduled_for = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(SQLEnum(FollowupStatus), default=FollowupStatus.pending, nullable=False)
    message = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    executed_at = Column(DateTime(timezone=True), nullable=True)

    # Relacionamento
    conversation = relationship("Conversation", backref="followups")