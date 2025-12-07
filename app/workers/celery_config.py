"""
Configuração do Celery para tarefas assíncronas
"""
from celery import Celery
from celery.schedules import crontab
from app.config import settings

# Inicializa Celery
celery_app = Celery(
    "whatsapp_agent",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# Configurações
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Sao_Paulo',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutos
    result_expires=3600,  # 1 hora
)

# Configuração de tasks periódicas (Celery Beat)
celery_app.conf.beat_schedule = {
    # Verificar follow-ups pendentes a cada 1 minuto
    'check-pending-followups': {
        'task': 'app.workers.followup_worker.check_pending_followups',
        'schedule': 60.0,  # 60 segundos
    },
    
    # Calcular métricas diárias às 00:05
    'calculate-daily-metrics': {
        'task': 'app.workers.metrics_worker.calculate_daily_metrics',
        'schedule': crontab(hour=0, minute=5),
    },
}

# IMPORTANTE: Importar os workers para registrar as tasks
from app.workers import followup_worker, metrics_worker