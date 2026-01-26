"""
Sistema de Métricas para Monitoramento
Expõe métricas no formato Prometheus
"""

from datetime import datetime, timedelta
from sqlalchemy import func
from app.database import SessionLocal
from app.models.conversation import Conversation, ConversationStatus
from app.models.message import Message
from app.models.metric import Metric


class MetricsCollector:
    """Coleta métricas do sistema"""
    
    @staticmethod
    def get_current_metrics():
        """Retorna métricas atuais do sistema"""
        db = SessionLocal()
        
        try:
            now = datetime.utcnow()
            today = now.date()
            last_hour = now - timedelta(hours=1)
            
            # Total de conversas ativas
            active_conversations = db.query(func.count(Conversation.id)).filter(
                Conversation.status == ConversationStatus.active
            ).scalar() or 0
            
            # Mensagens na última hora
            messages_last_hour = db.query(func.count(Message.id)).filter(
                Message.created_at >= last_hour
            ).scalar() or 0
            
            # Conversas criadas hoje
            conversations_today = db.query(func.count(Conversation.id)).filter(
                func.date(Conversation.created_at) == today
            ).scalar() or 0
            
            # Handoffs hoje
            handoffs_today = db.query(func.count(Conversation.id)).filter(
                func.date(Conversation.handoff_at) == today
            ).scalar() or 0
            
            # Métricas do dia (se existir)
            daily_metrics = db.query(Metric).filter(
                Metric.date == today
            ).first()
            
            return {
                "timestamp": now.isoformat(),
                "active_conversations": active_conversations,
                "messages_last_hour": messages_last_hour,
                "conversations_today": conversations_today,
                "handoffs_today": handoffs_today,
                "daily_metrics": {
                    "total_conversations": daily_metrics.total_conversations if daily_metrics else 0,
                    "total_messages": daily_metrics.total_messages if daily_metrics else 0,
                    "conversion_rate": daily_metrics.conversion_rate if daily_metrics else 0.0,
                    "avg_response_time": daily_metrics.avg_response_time if daily_metrics else 0.0
                } if daily_metrics else None
            }
            
        finally:
            db.close()
    
    @staticmethod
    def get_prometheus_format():
        """Retorna métricas no formato Prometheus"""
        metrics = MetricsCollector.get_current_metrics()
        
        lines = [
            "# HELP active_conversations Total de conversas ativas",
            "# TYPE active_conversations gauge",
            f"active_conversations {metrics['active_conversations']}",
            "",
            "# HELP messages_last_hour Mensagens na última hora",
            "# TYPE messages_last_hour gauge",
            f"messages_last_hour {metrics['messages_last_hour']}",
            "",
            "# HELP conversations_today Conversas criadas hoje",
            "# TYPE conversations_today gauge",
            f"conversations_today {metrics['conversations_today']}",
            "",
            "# HELP handoffs_today Handoffs realizados hoje",
            "# TYPE handoffs_today gauge",
            f"handoffs_today {metrics['handoffs_today']}",
        ]
        
        return "\n".join(lines)