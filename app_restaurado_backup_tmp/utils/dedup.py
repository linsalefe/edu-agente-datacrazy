import redis
from app.config import settings
from loguru import logger
import hashlib
from typing import Optional


class DedupManager:
    """Gerencia detecção de mensagens duplicadas usando Redis"""
    
    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.ttl = 12  # 12 segundos
    
    def _generate_hash(self, phone: str, text: str) -> str:
        """Gera hash único para phone + text"""
        content = f"{phone}:{text}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def is_duplicate(self, phone: str, text: str) -> bool:
        """
        Verifica se a mensagem é duplicata
        
        Args:
            phone: Número do telefone
            text: Texto da mensagem
            
        Returns:
            True se for duplicata
        """
        
        msg_hash = self._generate_hash(phone, text)
        key = f"dedup:{msg_hash}"
        
        try:
            # Verifica se já existe
            exists = self.redis_client.exists(key)
            
            if exists:
                logger.warning(f"⚠️  Mensagem duplicada detectada: {phone} - {text[:30]}...")
                return True
            
            # Marca como processada
            self.redis_client.setex(key, self.ttl, "1")
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar duplicata: {e}")
            # Em caso de erro, deixa passar (não bloqueia)
            return False
    
    def get_last_sent(self, phone: str) -> Optional[str]:
        """Retorna última mensagem enviada para este número"""
        key = f"last_sent:{phone}"
        try:
            value = self.redis_client.get(key)
            return value.decode() if value else None
        except Exception as e:
            logger.error(f"❌ Erro ao buscar última mensagem enviada: {e}")
            return None
    
    def set_last_sent(self, phone: str, text: str):
        """Armazena última mensagem enviada para detecção de loop"""
        key = f"last_sent:{phone}"
        try:
            self.redis_client.setex(key, self.ttl, text)
        except Exception as e:
            logger.error(f"❌ Erro ao armazenar última mensagem enviada: {e}")