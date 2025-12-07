"""
Scheduler de Follow-ups
Agenda follow-ups automáticos para conversas
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from loguru import logger

from app.models.followup import Followup, FollowupStatus, FollowupType
from app.models.conversation import Conversation
from app.workers.followup_worker import send_followup


class FollowupScheduler:
    """Gerenciador de agendamento de follow-ups"""
    
    @staticmethod
    def schedule_followups(conversation_id: int, db: Session):
        """
        Agenda todos os follow-ups para uma conversa
        
        Args:
            conversation_id: ID da conversa
            db: Sessão do banco de dados
        """
        logger.info(f"📅 Agendando follow-ups para conversa {conversation_id}")
        
        try:
            # Busca conversa
            conversation = db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if not conversation:
                logger.error(f"❌ Conversa {conversation_id} não encontrada")
                return
            
            now = datetime.utcnow()
            
            # Define os intervalos de follow-up
            followup_intervals = {
                FollowupType.THREE_HOURS: timedelta(hours=3),
                FollowupType.ONE_DAY: timedelta(days=1),
                FollowupType.THREE_DAYS: timedelta(days=3),
                FollowupType.SEVEN_DAYS: timedelta(days=7),
            }
            
            # Cria os follow-ups
            for followup_type, interval in followup_intervals.items():
                scheduled_for = now + interval
                
                followup = Followup(
                    conversation_id=conversation_id,
                    type=followup_type,
                    scheduled_for=scheduled_for,
                    status=FollowupStatus.PENDING,
                    message=f"Follow-up automático {followup_type.value}"
                )
                
                db.add(followup)
                logger.info(f"✅ Follow-up {followup_type.value} agendado para {scheduled_for}")
            
            db.commit()
            logger.info(f"✅ {len(followup_intervals)} follow-ups agendados")
            
        except Exception as e:
            logger.error(f"❌ Erro ao agendar follow-ups: {e}")
            db.rollback()
    
    @staticmethod
    def cancel_followups(conversation_id: int, db: Session):
        """
        Cancela todos os follow-ups pendentes de uma conversa
        
        Args:
            conversation_id: ID da conversa
            db: Sessão do banco de dados
        """
        logger.info(f"🚫 Cancelando follow-ups da conversa {conversation_id}")
        
        try:
            # Busca follow-ups pendentes
            pending = db.query(Followup).filter(
                Followup.conversation_id == conversation_id,
                Followup.status == FollowupStatus.PENDING
            ).all()
            
            # Cancela cada um
            for followup in pending:
                followup.status = FollowupStatus.CANCELLED
                logger.info(f"✅ Follow-up {followup.id} cancelado")
            
            db.commit()
            logger.info(f"✅ {len(pending)} follow-ups cancelados")
            
        except Exception as e:
            logger.error(f"❌ Erro ao cancelar follow-ups: {e}")
            db.rollback()
    
    @staticmethod
    def reschedule_followup(followup_id: int, new_time: datetime, db: Session):
        """
        Reagenda um follow-up específico
        
        Args:
            followup_id: ID do follow-up
            new_time: Nova data/hora
            db: Sessão do banco de dados
        """
        logger.info(f"🔄 Reagendando follow-up {followup_id}")
        
        try:
            followup = db.query(Followup).filter(
                Followup.id == followup_id
            ).first()
            
            if not followup:
                logger.error(f"❌ Follow-up {followup_id} não encontrado")
                return
            
            old_time = followup.scheduled_for
            followup.scheduled_for = new_time
            followup.status = FollowupStatus.PENDING
            
            db.commit()
            logger.info(f"✅ Follow-up reagendado: {old_time} → {new_time}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao reagendar follow-up: {e}")
            db.rollback()