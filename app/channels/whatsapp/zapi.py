import requests
from app.config import settings
from loguru import logger
from typing import Optional
import time


class ZAPIClient:
    """Cliente para integração com Z-API (WhatsApp)"""
    
    def __init__(self):
        self.token = settings.ZAPI_TOKEN
        self.instance = settings.ZAPI_INSTANCE
        self.client_token = settings.ZAPI_CLIENT_TOKEN
        # Formato correto da URL Z-API
        self.base_url = f"https://api.z-api.io/instances/{self.instance}/token/{self.token}"
        self.max_retries = 2
        self.retry_delay = 2
    
    def _make_request(self, endpoint: str, method: str = "POST", data: dict = None) -> Optional[dict]:
        """Faz requisição para Z-API com retry"""
        
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Client-Token": self.client_token,
            "Content-Type": "application/json"
        }
        
        for attempt in range(self.max_retries + 1):
            try:
                if method == "POST":
                    response = requests.post(url, json=data, headers=headers, timeout=10)
                elif method == "GET":
                    response = requests.get(url, headers=headers, timeout=10)
                
                # Log da requisição
                logger.info(f"📤 Z-API {method} {endpoint}: Status {response.status_code}")
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:  # Rate limit
                    logger.warning(f"⚠️  Rate limit Z-API. Tentativa {attempt + 1}/{self.max_retries + 1}")
                    time.sleep(self.retry_delay * 2)
                    continue
                else:
                    logger.error(f"❌ Erro Z-API: {response.status_code} - {response.text}")
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay)
                        continue
                    return None
                    
            except requests.exceptions.Timeout:
                logger.warning(f"⚠️  Timeout Z-API. Tentativa {attempt + 1}/{self.max_retries + 1}")
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
                    continue
                return None
                
            except Exception as e:
                logger.error(f"❌ Erro ao chamar Z-API: {e}")
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
                    continue
                return None
        
        return None
    
    def send_text(self, phone: str, message: str) -> bool:
        """
        Envia mensagem de texto
        
        Args:
            phone: Número com DDI (ex: 5583999999999)
            message: Texto da mensagem
            
        Returns:
            True se enviado com sucesso
        """
        
        data = {
            "phone": phone,
            "message": message
        }
        
        logger.info(f"📱 Enviando mensagem para {phone}")
        
        result = self._make_request("send-text", data=data)
        
        if result:
            logger.info(f"✅ Mensagem enviada para {phone}")
            return True
        else:
            logger.error(f"❌ Falha ao enviar mensagem para {phone}")
            return False
    
    def send_image(self, phone: str, image_url: str, caption: Optional[str] = None) -> bool:
        """
        Envia imagem com caption opcional
        
        Args:
            phone: Número com DDI
            image_url: URL da imagem
            caption: Legenda opcional
            
        Returns:
            True se enviado com sucesso
        """
        
        data = {
            "phone": phone,
            "image": image_url
        }
        
        if caption:
            data["caption"] = caption
        
        logger.info(f"📷 Enviando imagem para {phone}")
        
        result = self._make_request("send-image", data=data)
        
        if result:
            logger.info(f"✅ Imagem enviada para {phone}")
            return True
        else:
            logger.error(f"❌ Falha ao enviar imagem para {phone}")
            return False
    
    def get_instance_status(self) -> Optional[dict]:
        """
        Verifica status da instância Z-API
        
        Returns:
            Dados do status ou None
        """
        
        logger.info("🔍 Verificando status da instância...")
        
        result = self._make_request("status", method="GET")
        
        if result:
            connected = result.get("connected", False)
            status_msg = "✅ Conectado" if connected else "❌ Desconectado"
            logger.info(f"{status_msg}: {result}")
            return result
        else:
            logger.error("❌ Falha ao verificar status")
            return None