"""
Worker para envio de follow-ups automáticos
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from loguru import logger

from app.workers.celery_config import celery_app
from app.database import get_db
from app.models.followup import Followup, FollowupStatus, FollowupType
from app.models.conversation import Conversation, ConversationStatus
from app.channels.whatsapp.zapi import ZAPIClient
from app.config import settings


@celery_app.task(name='app.workers.followup_worker.send_followup')
def send_followup(followup_id: int):
    """
    Envia um follow-up específico
    
    Args:
        followup_id: ID do follow-up a ser enviado
    """
    logger.info(f"📬 Processando follow-up {followup_id}")
    
    db: Session = next(get_db())
    
    try:
        # Busca follow-up
        followup = db.query(Followup).filter(
            Followup.id == followup_id,
            Followup.status == FollowupStatus.pending
        ).first()
        
        if not followup:
            logger.warning(f"⚠️  Follow-up {followup_id} não encontrado ou já processado")
            return
        
        # Busca conversa
        conversation = db.query(Conversation).filter(
            Conversation.id == followup.conversation_id
        ).first()
        
        if not conversation:
            logger.error(f"❌ Conversa {followup.conversation_id} não encontrada")
            followup.status = FollowupStatus.cancelled
            db.commit()
            return
        
        # Verifica se cliente já respondeu (cancela follow-up)
        time_since_last_message = datetime.now(timezone.utc) - conversation.last_message_at
        if time_since_last_message < timedelta(hours=1):
            logger.info(f"✅ Cliente já respondeu - cancelando follow-up {followup_id}")
            followup.status = FollowupStatus.cancelled
            db.commit()
            return
        
        # Verifica se conversa foi para handoff (cancela follow-up)
        if conversation.status == ConversationStatus.handoff:
            logger.info(f"✅ Conversa em handoff - cancelando follow-up {followup_id}")
            followup.status = FollowupStatus.cancelled
            db.commit()
            return
        
        # Monta mensagem baseada no tipo
        message = get_followup_message(followup.type, conversation)
        
        # Envia via WhatsApp
        zapi = ZAPIClient()
        
        result = zapi.send_text(conversation.phone, message)
        
        if result:
            logger.info(f"✅ Follow-up {followup_id} enviado com sucesso")
            followup.status = FollowupStatus.sent
            followup.executed_at = datetime.now(timezone.utc)
        else:
            logger.error(f"❌ Falha ao enviar follow-up {followup_id}")
            followup.status = FollowupStatus.cancelled
        
        db.commit()
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar follow-up {followup_id}: {e}")
        db.rollback()
    finally:
        db.close()


@celery_app.task(name='app.workers.followup_worker.check_pending_followups')
def check_pending_followups():
    """
    Task periódica que verifica follow-ups pendentes
    Roda a cada 1 minuto via Celery Beat
    """
    logger.info("🔍 Verificando follow-ups pendentes...")
    
    db: Session = next(get_db())
    
    try:
        # Busca follow-ups que já passaram da hora agendada
        now = datetime.now(timezone.utc)
        pending = db.query(Followup).filter(
            Followup.status == FollowupStatus.pending,
            Followup.scheduled_for <= now
        ).all()
        
        logger.info(f"📊 Encontrados {len(pending)} follow-ups para processar")
        
        # Dispara task para cada follow-up
        for followup in pending:
            send_followup.delay(followup.id)
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar follow-ups: {e}")
    finally:
        db.close()


def get_followup_message(followup_type: FollowupType, conversation: Conversation) -> str:
    """
    Retorna mensagem de follow-up baseada no tipo
    
    Args:
        followup_type: Tipo do follow-up (3h, 1d, 3d, 7d)
        conversation: Conversa associada
    
    Returns:
        Mensagem a ser enviada
    """
    messages = {
        FollowupType.three_hours: f"""
Olá! 👋

Vi que você demonstrou interesse em fazer faculdade conosco há algumas horas.

Ainda tem alguma dúvida? Estou aqui para ajudar! 😊
        """.strip(),
        
        FollowupType.one_day: f"""
Oi! Como vai? 

Não queria deixar sua dúvida sem resposta! 

Sobre a faculdade que você perguntou, posso te passar mais informações?

📚 Temos opções incríveis que podem se encaixar no seu perfil!
        """.strip(),
        
        FollowupType.three_days: f"""
Olá! 

Percebi que você estava interessado em começar uma graduação.

🎓 Esse é um passo importante e quero te ajudar a tomar a melhor decisão!

Posso tirar suas dúvidas? Temos condições especiais agora!
        """.strip(),
        
        FollowupType.seven_days: f"""
Oi! Tudo bem?

Vi que você demonstrou interesse em fazer faculdade há uma semana.

💡 Queria saber se ainda tem interesse? 

Posso te passar informações sobre:
✅ Cursos disponíveis
✅ Valores e formas de pagamento
✅ Processo de matrícula

O que acha?
        """.strip(),
    }
    
    return messages.get(followup_type, messages[FollowupType.one_day])
