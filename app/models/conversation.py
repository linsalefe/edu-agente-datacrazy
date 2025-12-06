from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, Index
from sqlalchemy.sql import func
from datetime import datetime, timedelta
import enum
from app.database import Base


class ConversationStatus(enum.Enum):
    active = "active"
    paused = "paused"
    handoff = "handoff"
    closed = "closed"


class ConversationStage(enum.Enum):
    novo = "novo"
    atendimento = "atendimento"
    qualificacao = "qualificacao"
    negociacao = "negociacao"
    fechamento = "fechamento"
    pos_venda = "pos_venda"


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), nullable=False, index=True)
    lead_id = Column(Integer, nullable=True)
    status = Column(SQLEnum(ConversationStatus), default=ConversationStatus.active, nullable=False)
    current_stage = Column(SQLEnum(ConversationStage), default=ConversationStage.novo, nullable=False)
    
    last_message_at = Column(DateTime(timezone=True), server_default=func.now())
    handoff_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Índices compostos
    __table_args__ = (
        Index('idx_phone_status', 'phone', 'status'),
        Index('idx_created_at', 'created_at'),
    )

    def is_active(self):
        """Verifica se a conversa está ativa"""
        return self.status == ConversationStatus.active

    def time_since_last_message(self):
        """Retorna tempo desde última mensagem em minutos"""
        if self.last_message_at:
            delta = datetime.now() - self.last_message_at.replace(tzinfo=None)
            return delta.total_seconds() / 60
        return 0