"""
Cliente para API do DataCrazy CRM
URL: https://api.g1.datacrazy.io/api/v1
Documentação: https://datacrazy.mintlify.app/
"""

import requests
from typing import Dict, Optional
from loguru import logger
import time


class DataCrazyClient:
    """Cliente para API do DataCrazy CRM"""
    
    def __init__(self, api_token: str, base_url: str = None):
        self.api_token = api_token
        # URL CORRETA da API DataCrazy
        self.base_url = base_url or "https://api.g1.datacrazy.io/api/v1"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        max_retries: int = 3
    ) -> Dict:
        """Faz requisição com retry automático"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        for attempt in range(max_retries):
            try:
                if method == "GET":
                    response = self.session.get(url, params=params, timeout=10)
                elif method == "POST":
                    response = self.session.post(url, json=data, timeout=10)
                elif method == "PATCH":
                    response = self.session.patch(url, json=data, timeout=10)
                elif method == "DELETE":
                    response = self.session.delete(url, timeout=10)
                else:
                    raise ValueError(f"Método HTTP inválido: {method}")
                
                logger.info(f"📤 DataCrazy {method} {endpoint}: Status {response.status_code}")
                
                # Trata sucesso
                if 200 <= response.status_code < 300:
                    if response.content:
                        return response.json()
                    return {"success": True}
                
                # Trata rate limit
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"⚠️  Rate limit - aguardando {wait_time}s")
                        time.sleep(wait_time)
                        continue
                
                # Trata outros erros
                try:
                    error_data = response.json()
                except:
                    error_data = response.text[:500]
                
                logger.error(f"❌ Erro DataCrazy: {response.status_code} - {error_data}")
                response.raise_for_status()
                
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    logger.warning(f"⏱️  Timeout - tentativa {attempt + 2}/{max_retries}")
                    time.sleep(1)
                    continue
                raise
            
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    logger.warning(f"🔄 Erro de rede - tentativa {attempt + 2}/{max_retries}")
                    time.sleep(2 ** attempt)
                    continue
                raise
        
        raise Exception("Máximo de tentativas excedido")
    
    # ========== LEADS ==========
    
    def create_lead(self, data: Dict) -> Dict:
        """
        Cria um novo lead
        
        Args:
            data: {
                "name": str (obrigatório),
                "phone": str (opcional),
                "email": str (opcional),
                "company": str (opcional),
                "source": str (opcional)
            }
        """
        logger.info(f"📝 Criando lead: {data.get('name')} - {data.get('phone')}")
        
        try:
            result = self._make_request("POST", "leads", data=data)
            logger.info(f"✅ Lead criado com sucesso: ID {result.get('id')}")
            return result
        except Exception as e:
            logger.error(f"❌ Falha ao criar lead no DataCrazy")
            raise
    
    def update_lead(self, lead_id: str, data: Dict) -> Dict:
        """Atualiza um lead existente"""
        logger.info(f"🔄 Atualizando lead {lead_id}")
        return self._make_request("PATCH", f"leads/{lead_id}", data=data)
    
    def get_lead(self, lead_id: str) -> Dict:
        """Busca informações de um lead"""
        return self._make_request("GET", f"leads/{lead_id}")
    
    def list_leads(self, params: Optional[Dict] = None) -> Dict:
        """Lista leads com filtros opcionais"""
        return self._make_request("GET", "leads", params=params)
    
    # ========== NEGÓCIOS ==========
    
    def create_deal(self, lead_id: str, pipeline_id: str, stage_id: str, data: Dict) -> Dict:
        """
        Cria um negócio para um lead
        
        Args:
            lead_id: ID do lead
            pipeline_id: ID do pipeline
            stage_id: ID do estágio
            data: Dados adicionais do negócio
        """
        payload = {
            "pipelineId": pipeline_id,
            "stageId": stage_id,
            **data
        }
        logger.info(f"💼 Criando negócio para lead {lead_id}")
        return self._make_request("POST", f"leads/{lead_id}/deals", data=payload)
    
    def update_deal(self, deal_id: str, data: Dict) -> Dict:
        """Atualiza um negócio"""
        logger.info(f"🔄 Atualizando negócio {deal_id}")
        return self._make_request("PATCH", f"deals/{deal_id}", data=data)
    
    # ========== ANOTAÇÕES ==========
    
    def add_note(self, lead_id: str, content: str) -> Dict:
        """
        Adiciona uma anotação ao lead
        
        Args:
            lead_id: ID do lead
            content: Conteúdo da nota
        
        CAMPO CORRETO: "note" (confirmado na documentação oficial)
        https://datacrazy.mintlify.app/api-reference/anotações-do-lead/adicionar-comentário
        """
        data = {"note": content}
        logger.info(f"📝 Adicionando nota ao lead {lead_id}")
        return self._make_request("POST", f"leads/{lead_id}/notes", data=data)
    
    # ========== ATIVIDADES ==========
    
    def create_activity(self, lead_id: str, data: Dict) -> Dict:
        """
        Cria uma atividade para um lead
        
        Args:
            lead_id: ID do lead
            data: {
                "title": str,
                "description": str,
                "dueDate": str (ISO format),
                "type": str
            }
        """
        logger.info(f"📅 Criando atividade para lead {lead_id}: {data.get('title')}")
        return self._make_request("POST", f"leads/{lead_id}/activities", data=data)
    
    # ========== TAGS ==========
    
    def add_tags(self, lead_id: str, tag_ids: list) -> Dict:
        """Adiciona tags a um lead"""
        data = {"tags": [{"id": tag_id} for tag_id in tag_ids]}
        return self._make_request("POST", f"leads/{lead_id}/tags", data=data)
    
    # ========== HEALTH CHECK ==========
    
    def health_check(self) -> bool:
        """Verifica se a conexão com a API está funcionando"""
        try:
            self.list_leads(params={"page": 1, "perPage": 1})
            logger.info("✅ Conexão DataCrazy OK")
            return True
        except Exception as e:
            logger.error(f"❌ Falha na conexão DataCrazy: {e}")
            return False