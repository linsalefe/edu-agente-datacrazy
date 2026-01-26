from openai import OpenAI
from app.config import settings
from loguru import logger
import time
from typing import List, Dict, Optional


class OpenAIClient:
    """Cliente OpenAI com retry automático e tratamento de erros"""
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super(OpenAIClient, cls).__new__(cls)
            cls._instance.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            cls._instance.total_tokens = 0
        return cls._instance
    
    def chat_completion(
        self, 
        messages: List[Dict], 
        temperature: float = 0.7,
        max_tokens: int = 500,
        model: str = "gpt-4o-mini"
    ) -> Optional[str]:
        """
        Gera resposta usando chat completion com retry automático
        
        Args:
            messages: Lista de mensagens no formato OpenAI
            temperature: Criatividade (0-2)
            max_tokens: Máximo de tokens na resposta
            model: Modelo a usar
            
        Returns:
            Resposta do modelo ou None em caso de erro
        """
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                # Contabilizar tokens
                usage = response.usage
                self.total_tokens += usage.total_tokens
                
                logger.info(f"✅ OpenAI: {usage.total_tokens} tokens usados (total: {self.total_tokens})")
                
                return response.choices[0].message.content
                
            except Exception as e:
                error_msg = str(e)
                
                # Rate limit - aguardar mais tempo
                if "rate_limit" in error_msg.lower():
                    wait_time = retry_delay * (attempt + 2)
                    logger.warning(f"⚠️  Rate limit atingido. Aguardando {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                # Timeout - tentar novamente
                elif "timeout" in error_msg.lower():
                    logger.warning(f"⚠️  Timeout. Tentativa {attempt + 1}/{max_retries}")
                    time.sleep(retry_delay)
                    continue
                
                # API down - aguardar
                elif "connection" in error_msg.lower() or "unavailable" in error_msg.lower():
                    logger.warning(f"⚠️  API indisponível. Tentativa {attempt + 1}/{max_retries}")
                    time.sleep(retry_delay * 2)
                    continue
                
                # Outros erros - falhar
                else:
                    logger.error(f"❌ Erro OpenAI: {e}")
                    if attempt == max_retries - 1:
                        return None
                    time.sleep(retry_delay)
        
        logger.error("❌ Falha após todas as tentativas")
        return None
    
    def get_total_tokens(self) -> int:
        """Retorna total de tokens usados"""
        return self.total_tokens