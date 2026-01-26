from app.utils.dedup import DedupManager
from loguru import logger


class AntiLoopManager:
    """Detecta e previne loops de conversa (bot respondendo a si mesmo)"""
    
    def __init__(self):
        self.dedup = DedupManager()
    
    def is_loop(self, phone: str, received_text: str) -> bool:
        """
        Detecta se a mensagem recebida é um eco da nossa resposta
        
        Args:
            phone: Número do telefone
            received_text: Texto recebido do usuário
            
        Returns:
            True se detectar loop
        """
        
        # Buscar última mensagem que enviamos para este número
        last_sent = self.dedup.get_last_sent(phone)
        
        if not last_sent:
            return False
        
        # Se o texto recebido é exatamente igual ao que enviamos
        if received_text.strip() == last_sent.strip():
            logger.warning(f"🔄 Loop detectado para {phone}: mensagem idêntica")
            return True
        
        return False
    
    def register_sent_message(self, phone: str, text: str):
        """Registra mensagem enviada para detecção futura de loops"""
        self.dedup.set_last_sent(phone, text)