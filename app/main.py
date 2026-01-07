from fastapi import FastAPI, Request, BackgroundTasks
from app.config import settings
from app.services.message_processor import MessageProcessor
from app.database import get_db
from loguru import logger

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