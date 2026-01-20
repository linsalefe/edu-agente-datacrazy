"""
🔒 BACKUP - 20/01/2026
"""

from fastapi import FastAPI, Request, BackgroundTasks
from datetime import datetime
from sqlalchemy import text
import redis

from app.config import settings
from app.services.message_processor import MessageProcessor
from app.database import get_db
from app.utils.logger import logger
from app.utils.metrics import MetricsCollector
from app.channels.whatsapp.zapi import ZAPIClient
from app.crm.datacrazy import DataCrazyClient

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


@app.get("/metrics")
async def metrics():
    """Endpoint de métricas para monitoramento (Prometheus)"""
    return MetricsCollector.get_prometheus_format()


@app.get("/health/detailed")
async def health_detailed():
    """Health check detalhado com status de dependências"""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    # Check Database
    try:
        db = next(get_db())
        db.execute(text("SELECT 1"))
        health_status["checks"]["database"] = "healthy"
        db.close()
    except Exception as e:
        health_status["checks"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Check Redis
    try:
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        health_status["checks"]["redis"] = "healthy"
    except Exception as e:
        health_status["checks"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Check Z-API
    try:
        zapi = ZAPIClient()
        status = zapi.get_instance_status()
        health_status["checks"]["zapi"] = "healthy" if status else "unhealthy"
    except Exception as e:
        health_status["checks"]["zapi"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check DataCrazy
    try:
        crm = DataCrazyClient(api_token=settings.DATACRAZY_API_TOKEN)
        if crm.health_check():
            health_status["checks"]["datacrazy"] = "healthy"
        else:
            health_status["checks"]["datacrazy"] = "unhealthy"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["checks"]["datacrazy"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    return health_status


async def process_message_background(phone: str, text: str, name: str):
    """Processa mensagem em background"""
    db = next(get_db())
    try:
        processor = MessageProcessor(db)
        await processor.process_message(phone, text, name)
    finally:
        db.close()


@app.post("/webhook")
async def webhook_receiver(request: Request, background_tasks: BackgroundTasks):
    """
    Recebe webhooks do Z-API com mensagens do WhatsApp
    """
    try:
        payload = await request.json()
        
        # Log do webhook recebido
        logger.info(f"📥 Webhook recebido: {payload.get('event', 'unknown')}")
        
        # Extrair dados principais
        phone = payload.get('phone')
        text = payload.get('text', {}).get('message', '')
        from_me = payload.get('fromMe', False)
        sender_name = payload.get('senderName', '')
        
        # Ignorar mensagens próprias
        if from_me:
            logger.info("⏭️  Mensagem própria ignorada")
            return {"status": "ignored", "reason": "from_me"}
        
        # Validar campos obrigatórios
        if not phone or not text:
            logger.warning("⚠️  Webhook sem phone ou texto")
            return {"status": "ignored", "reason": "missing_fields"}
        
        # Log da mensagem
        logger.info(f"💬 Nova mensagem de {sender_name} ({phone}): {text[:50]}...")
        
        # Processar mensagem em background
        background_tasks.add_task(process_message_background, phone, text, sender_name)
        
        # Retornar 200 imediatamente
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar webhook: {e}")
        return {"status": "error", "message": str(e)}
