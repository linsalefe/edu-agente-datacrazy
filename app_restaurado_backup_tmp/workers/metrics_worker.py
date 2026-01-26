"""
Worker para cálculo de métricas diárias
"""

from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from loguru import logger

from app.workers.celery_config import celery_app
from app.database import get_db
from app.models.metric import Metric
from app.models.conversation import Conversation, ConversationStatus
from app.models.message import Message
from app.models.lead import Lead


@celery_app.task(name='app.workers.metrics_worker.calculate_daily_metrics')
def calculate_daily_metrics(target_date: str = None):
    """
    Calcula métricas do dia anterior
    Roda automaticamente às 00:05 todos os dias via Celery Beat
    
    Args:
        target_date: Data alvo no formato YYYY-MM-DD (opcional)
    """
    db: Session = next(get_db())
    
    try:
        # Define a data alvo (ontem por padrão)
        if target_date:
            metric_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        else:
            metric_date = date.today() - timedelta(days=1)
        
        logger.info(f"📊 Calculando métricas para {metric_date}")
        
        # Define range de datas (início e fim do dia)
        start_of_day = datetime.combine(metric_date, datetime.min.time())
        end_of_day = datetime.combine(metric_date, datetime.max.time())
        
        # 1. Total de conversas do dia
        total_conversations = db.query(func.count(Conversation.id)).filter(
            Conversation.created_at >= start_of_day,
            Conversation.created_at <= end_of_day
        ).scalar() or 0
        
        # 2. Total de mensagens do dia
        total_messages = db.query(func.count(Message.id)).filter(
            Message.created_at >= start_of_day,
            Message.created_at <= end_of_day
        ).scalar() or 0
        
        # 3. Conversas que foram para handoff
        handoff_count = db.query(func.count(Conversation.id)).filter(
            Conversation.handoff_at >= start_of_day,
            Conversation.handoff_at <= end_of_day
        ).scalar() or 0
        
        # 4. Taxa de conversão (conversas ativas / total de conversas)
        active_conversations = db.query(func.count(Conversation.id)).filter(
            Conversation.created_at >= start_of_day,
            Conversation.created_at <= end_of_day,
            Conversation.status == ConversationStatus.active
        ).scalar() or 0
        
        conversion_rate = (active_conversations / total_conversations * 100) if total_conversations > 0 else 0.0
        
        # 5. Tempo médio de resposta (em segundos)
        conversations_with_messages = db.query(Conversation).filter(
            Conversation.created_at >= start_of_day,
            Conversation.created_at <= end_of_day
        ).all()
        
        response_times = []
        for conv in conversations_with_messages:
            messages = db.query(Message).filter(
                Message.conversation_id == conv.id
            ).order_by(Message.created_at).limit(2).all()
            
            if len(messages) >= 2:
                time_diff = (messages[1].created_at - messages[0].created_at).total_seconds()
                response_times.append(time_diff)
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0
        
        # Verifica se já existe métrica para esse dia
        existing = db.query(Metric).filter(Metric.date == metric_date).first()
        
        if existing:
            # Atualiza
            existing.total_conversations = total_conversations
            existing.total_messages = total_messages
            existing.handoff_count = handoff_count
            existing.conversion_rate = conversion_rate
            existing.avg_response_time = avg_response_time
            logger.info(f"🔄 Métricas atualizadas para {metric_date}")
        else:
            # Cria nova
            metric = Metric(
                date=metric_date,
                total_conversations=total_conversations,
                total_messages=total_messages,
                handoff_count=handoff_count,
                conversion_rate=conversion_rate,
                avg_response_time=avg_response_time
            )
            db.add(metric)
            logger.info(f"✅ Métricas criadas para {metric_date}")
        
        db.commit()
        
        # Log resumo
        logger.info(f"""
📊 RESUMO DE MÉTRICAS - {metric_date}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📞 Conversas: {total_conversations}
💬 Mensagens: {total_messages}
🤝 Handoffs: {handoff_count}
📈 Taxa Conversão: {conversion_rate:.2f}%
⏱️  Tempo Resposta: {avg_response_time:.2f}s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """)
        
        return {
            "date": str(metric_date),
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "handoff_count": handoff_count,
            "conversion_rate": conversion_rate,
            "avg_response_time": avg_response_time
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao calcular métricas: {e}")
        db.rollback()
        raise
    finally:
        db.close()