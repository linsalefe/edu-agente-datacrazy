"""
Serviço de Handoff
Gerencia transferência de conversas para atendimento humano
"""
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from loguru import logger

from app.models.conversation import Conversation, ConversationStatus
from app.core.scheduler import FollowupScheduler
from app.channels.whatsapp.zapi import ZAPIClient
from app.crm.sync_service import CRMSyncService
from app.config import settings


class HandoffService:
    """Gerenciador de handoffs (transferência para humano)"""
    
    @staticmethod
    def request_handoff(conversation_id: int, reason: str, db: Session):
        """
        Solicita handoff de uma conversa
        
        Args:
            conversation_id: ID da conversa
            reason: Motivo do handoff
            db: Sessão do banco de dados
        """
        logger.info(f"🤝 Solicitando handoff para conversa {conversation_id}")
        logger.info(f"   Motivo: {reason}")
        
        try:
            # Busca conversa
            conversation = db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if not conversation:
                logger.error(f"❌ Conversa {conversation_id} não encontrada")
                return False
            
            # Atualiza status da conversa
            conversation.status = ConversationStatus.handoff
            conversation.handoff_at = datetime.now(timezone.utc)
            
            # Cancela follow-ups pendentes
            FollowupScheduler.cancel_followups(conversation_id, db)
            
            # Notifica cliente
            HandoffService._notify_client(conversation, db)
            
            # Notifica atendente
            HandoffService._notify_attendant(conversation, reason, db)
            
            # Sincroniza com CRM
            try:
                crm = CRMSyncService(db)
                crm.add_note_to_lead(
                    conversation.lead_id,
                    f"🤝 HANDOFF SOLICITADO\nMotivo: {reason}\nData: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')}"
                )
            except Exception as e:
                logger.warning(f"⚠️  Erro ao sincronizar handoff com CRM: {e}")
            
            db.commit()
            logger.info(f"✅ Handoff registrado com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar handoff: {e}")
            db.rollback()
            return False
    
    @staticmethod
    def _notify_client(conversation: Conversation, db: Session):
        """Notifica cliente sobre handoff"""
        try:
            zapi = ZAPIClient()
            
            message = """
Entendo sua situação! 😊

Vou transferir você para um de nossos consultores especializados que poderá te ajudar melhor com isso.

⏱️ Em breve alguém da nossa equipe entrará em contato!

Obrigado pela paciência! 🙏
            """.strip()
            
            zapi.send_text(conversation.phone, message)
            logger.info(f"✅ Cliente notificado sobre handoff")
            
        except Exception as e:
            logger.error(f"❌ Erro ao notificar cliente: {e}")
    
    @staticmethod
    def _notify_attendant(conversation: Conversation, reason: str, db: Session):
        """Notifica atendente sobre novo handoff"""
        try:
            # Implementação de notificação para atendente
            # Pode ser via WhatsApp, email, Slack, etc
            logger.info(f"📝 Handoff registrado - implementar notificação de atendente")
            
        except Exception as e:
            logger.error(f"❌ Erro ao notificar atendente: {e}")