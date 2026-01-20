"""
🔒 BACKUP - 20/01/2026
"""

from typing import Optional, Dict, Any, List
from loguru import logger
import requests
from app.config import settings
from app.crm.datacrazy import DataCrazyClient
from app.models.lead import Lead
from app.models.conversation import Conversation, ConversationStage


class CRMSyncService:
    """Serviço de sincronização com DataCrazy CRM"""
    
    # ID da pipeline "IA - Bia" (fixo)
    PIPELINE_ID = "89e78ad1-2aa9-46d2-b692-28b7e689692b"
    
    # Cache dos estágios da pipeline (carregado uma vez)
    _stages_cache: Dict[str, str] = {}
    
    # Mapeamento: estágio interno → nome do estágio na pipeline
    STAGE_MAPPING = {
        "novo": "Entrada do Lead",
        "atendimento": "Em conversa",
        "qualificacao": "Lead Interessado",
        "negociacao": "Lead Interessado",
        "fechamento": "Fechamento",
        "pos_venda": "Fechamento",
    }
    
    def __init__(self, db):
        self.crm = DataCrazyClient(
            api_token=settings.DATACRAZY_API_TOKEN,
            base_url=settings.DATACRAZY_BASE_URL
        )
        self.db = db
        
        # Carrega os estágios da pipeline no cache
        if not CRMSyncService._stages_cache:
            self._load_pipeline_stages()
    
    def _load_pipeline_stages(self):
        """Carrega os estágios da pipeline no cache"""
        try:
            stages = self.crm.get_pipeline_stages(self.PIPELINE_ID)
            
            for stage in stages:
                stage_name = stage.get("name", "")
                stage_id = stage.get("id", "")
                if stage_name and stage_id:
                    CRMSyncService._stages_cache[stage_name] = stage_id
                    logger.info(f"📍 Estágio carregado: {stage_name} → {stage_id}")
            
            logger.info(f"✅ {len(CRMSyncService._stages_cache)} estágios carregados no cache")
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar estágios da pipeline: {e}")
    
    def _get_stage_id_by_name(self, stage_name: str) -> Optional[str]:
        """Busca ID do estágio pelo nome"""
        return CRMSyncService._stages_cache.get(stage_name)
    
    def _get_stage_id_for_internal_stage(self, internal_stage: str) -> Optional[str]:
        """
        Converte estágio interno do bot para ID do estágio na pipeline
        
        Args:
            internal_stage: Estágio interno (novo, atendimento, qualificacao, fechamento)
        
        Returns:
            ID do estágio na pipeline DataCrazy
        """
        pipeline_stage_name = self.STAGE_MAPPING.get(internal_stage)
        if not pipeline_stage_name:
            logger.warning(f"⚠️  Estágio interno '{internal_stage}' não mapeado")
            return None
        
        stage_id = self._get_stage_id_by_name(pipeline_stage_name)
        if not stage_id:
            logger.warning(f"⚠️  Estágio '{pipeline_stage_name}' não encontrado na pipeline")
            return None
        
        return stage_id
    
    # -------------------------
    # Helpers
    # -------------------------
    
    def _get_lead(self, lead_id: int) -> Optional[Lead]:
        lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            logger.error(f"❌ Lead {lead_id} não encontrado no banco")
        return lead
    
    def _extract_datacrazy_id(self, result: Any) -> Optional[str]:
        """
        Extrai ID do lead retornado pela API.
        Suporta:
          - {"data": {"id": "..."}}
          - {"id": "..."}
        """
        if not isinstance(result, dict):
            return None
        
        data = result.get("data")
        if isinstance(data, dict) and data.get("id"):
            return str(data["id"])
        
        if result.get("id"):
            return str(result["id"])
        
        return None
    
    def _find_existing_lead_id_by_phone(self, phone: str) -> Optional[str]:
        """
        Busca lead existente no DataCrazy via GET /leads?search=<phone>.
        Retorna o id do primeiro lead encontrado.
        """
        try:
            if not phone:
                return None
            
            result = self.crm.search_leads(search=phone, take=1, skip=0)
            if not isinstance(result, dict):
                return None
            
            data = result.get("data")
            if isinstance(data, list) and len(data) > 0:
                lead_obj = data[0]
                if isinstance(lead_obj, dict) and lead_obj.get("id"):
                    return str(lead_obj["id"])
            
            return None
        
        except Exception as e:
            logger.exception(f"❌ Erro ao buscar lead existente por telefone ({phone}): {e}")
            return None
    
    def _ensure_datacrazy_id(self, lead_id: int) -> Optional[str]:
        lead = self._get_lead(lead_id)
        if not lead:
            return None
        
        if lead.datacrazy_id:
            return str(lead.datacrazy_id)
        
        logger.warning(f"⚠️  Lead {lead_id} sem datacrazy_id, criando/recuperando no DataCrazy...")
        ok = self.sync_lead_create(lead_id)
        if not ok:
            return None
        
        lead = self._get_lead(lead_id)
        if not lead or not lead.datacrazy_id:
            logger.error(f"❌ Não foi possível persistir datacrazy_id para lead {lead_id}")
            return None
        
        return str(lead.datacrazy_id)
    
    def _get_pipeline_and_stage(self) -> tuple[Optional[str], Optional[str]]:
        """
        Retorna (pipeline_id, primeiro_stage_id) da pipeline 'IA - Bia'
    
        Returns:
            (pipeline_id, stage_id) ou (None, None) se não encontrar
        """
        try:
            pipeline_id = self.PIPELINE_ID
            
            # Buscar o primeiro estágio
            first_stage_name = "Entrada do Lead"
            stage_id = self._get_stage_id_by_name(first_stage_name)
            
            if not stage_id:
                # Fallback: pega o primeiro estágio disponível
                if CRMSyncService._stages_cache:
                    stage_id = list(CRMSyncService._stages_cache.values())[0]
                else:
                    logger.error("❌ Nenhum estágio encontrado na pipeline")
                    return None, None
            
            logger.info(f"✅ Pipeline: {pipeline_id}, Estágio inicial: {stage_id}")
            return str(pipeline_id), str(stage_id)
    
        except Exception as e:
            logger.exception(f"❌ Erro ao buscar pipeline e estágio: {e}")
            return None, None
    
    def _get_deal_id_for_lead(self, datacrazy_lead_id: str) -> Optional[str]:
        """
        Busca o ID do negócio (deal) associado ao lead
        
        Args:
            datacrazy_lead_id: ID do lead no DataCrazy
        
        Returns:
            ID do negócio ou None
        """
        try:
            result = self.crm.list_deals_by_lead(datacrazy_lead_id)
            
            deals = []
            if isinstance(result, dict):
                deals = result.get("data", [])
            elif isinstance(result, list):
                deals = result
            
            if deals and len(deals) > 0:
                # Retorna o primeiro negócio encontrado
                deal = deals[0]
                deal_id = deal.get("id")
                if deal_id:
                    return str(deal_id)
            
            return None
        
        except Exception as e:
            logger.warning(f"⚠️  Erro ao buscar negócio do lead {datacrazy_lead_id}: {e}")
            return None
    
    def _create_deal_for_lead(self, datacrazy_lead_id: str, lead_name: str) -> Optional[str]:
        """
        Cria um deal para o lead na pipeline 'IA - Bia'
        
        Args:
            datacrazy_lead_id: ID do lead no DataCrazy
            lead_name: Nome do lead (para o título do deal)
        
        Returns:
            ID do deal criado ou None
        """
        try:
            # Buscar pipeline e estágio
            pipeline_id, stage_id = self._get_pipeline_and_stage()
            
            if not pipeline_id or not stage_id:
                logger.warning(f"⚠️  Não foi possível criar deal - pipeline/stage não encontrados")
                return None
            
            # Criar deal
            deal_data = {
                "title": f"Atendimento IA - {lead_name}",
                "value": 0,
                "probability": 25
            }
            
            result = self.crm.create_deal(
                lead_id=datacrazy_lead_id,
                pipeline_id=pipeline_id,
                stage_id=stage_id,
                data=deal_data
            )
            
            if result:
                deal_id = self._extract_datacrazy_id(result)
                logger.info(f"💼 Deal criado com sucesso: {deal_id}")
                return deal_id
            
            logger.error(f"❌ Falha ao criar deal para lead {datacrazy_lead_id}")
            return None
        
        except Exception as e:
            logger.exception(f"❌ Erro ao criar deal para lead {datacrazy_lead_id}: {e}")
            return None
    
    # -------------------------
    # Movimentação na Pipeline
    # -------------------------
    
    def move_lead_in_pipeline(self, lead_id: int, new_stage: str) -> bool:
        """
        Move o card do lead para outro estágio na pipeline do DataCrazy
        
        Args:
            lead_id: ID do lead no banco local
            new_stage: Novo estágio interno (novo, atendimento, qualificacao, fechamento)
        
        Returns:
            True se moveu com sucesso
        """
        try:
            # 1. Garantir que o lead tem datacrazy_id
            datacrazy_id = self._ensure_datacrazy_id(lead_id)
            if not datacrazy_id:
                logger.warning(f"⚠️  Lead {lead_id} sem datacrazy_id - não pode mover na pipeline")
                return False
            
            # 2. Buscar o deal associado ao lead
            deal_id = self._get_deal_id_for_lead(datacrazy_id)
            
            if not deal_id:
                logger.warning(f"⚠️  Lead {lead_id} sem deal - criando...")
                lead = self._get_lead(lead_id)
                deal_id = self._create_deal_for_lead(datacrazy_id, lead.name or "Lead")
                
                if not deal_id:
                    logger.error(f"❌ Não foi possível criar deal para lead {lead_id}")
                    return False
            
            # 3. Converter estágio interno para ID do estágio na pipeline
            stage_id = self._get_stage_id_for_internal_stage(new_stage)
            
            if not stage_id:
                logger.warning(f"⚠️  Não foi possível mapear estágio '{new_stage}' para pipeline")
                return False
            
            # 4. Mover o deal para o novo estágio
            self.crm.move_deal_to_stage(deal_id, stage_id)
            
            pipeline_stage_name = self.STAGE_MAPPING.get(new_stage, new_stage)
            logger.info(f"✅ Lead {lead_id} movido para '{pipeline_stage_name}' na pipeline")
            
            return True
        
        except Exception as e:
            logger.exception(f"❌ Erro ao mover lead {lead_id} na pipeline: {e}")
            return False
    
    # -------------------------
    # Create
    # -------------------------
    
    def sync_lead_create(self, lead_id: int) -> bool:
        """
        Cria lead no DataCrazy e automaticamente cria um deal na pipeline.
        Se já existir (duplicado), busca e salva o ID existente.
        """
        lead = self._get_lead(lead_id)
        if not lead:
            return False
        
        if lead.datacrazy_id:
            logger.info(f"⏭️  Lead {lead_id} já tem datacrazy_id: {lead.datacrazy_id}")
            return True
        
        data = {
            "name": lead.name or "Lead sem nome",
            "phone": lead.phone,
            "email": lead.email,
            "origin": lead.origin or "whatsapp",
        }
        
        if getattr(lead, "profile", None):
            data["custom_fields"] = lead.profile
        
        try:
            result = self.crm.create_lead(data)
            
            datacrazy_id = self._extract_datacrazy_id(result)
            if datacrazy_id:
                lead.datacrazy_id = datacrazy_id
                self.db.add(lead)
                self.db.commit()
                logger.info(f"✅ Lead {lead_id} criado no DataCrazy: {datacrazy_id}")
                
                # Criar deal automaticamente
                self._create_deal_for_lead(datacrazy_id, lead.name or "Lead sem nome")
                
                return True
            
            logger.error(f"❌ create_lead retornou sem id. Resposta: {result}")
            return False
        
        except requests.exceptions.HTTPError as e:
            resp = getattr(e, "response", None)
            payload = None
            try:
                if resp is not None:
                    payload = resp.json()
            except Exception:
                payload = None
            
            # Detecta duplicidade
            code = None
            try:
                if isinstance(payload, dict):
                    code = payload.get("code") or payload.get("message", {}).get("code")
            except Exception:
                code = None
            
            if code == "lead-with-same-contact-exists":
                logger.warning(f"🔁 Lead já existe no DataCrazy. Buscando ID por telefone: {lead.phone}")
                existing_id = self._find_existing_lead_id_by_phone(str(lead.phone))
                if existing_id:
                    lead.datacrazy_id = existing_id
                    self.db.add(lead)
                    self.db.commit()
                    logger.info(f"✅ Lead {lead_id} já existia. ID recuperado e salvo: {existing_id}")
                    
                    # Criar deal para lead existente também
                    self._create_deal_for_lead(existing_id, lead.name or "Lead sem nome")
                    
                    return True
                
                logger.error(f"❌ Lead duplicado, mas não consegui localizar via search. Payload: {payload}")
                return False
            
            logger.exception(f"❌ HTTPError ao criar lead {lead_id}: {e} | payload={payload}")
            self.db.rollback()
            return False
        
        except Exception as e:
            logger.exception(f"❌ Erro ao sincronizar lead {lead_id}: {e}")
            self.db.rollback()
            return False
    
    # -------------------------
    # Update
    # -------------------------
    
    def sync_lead_update(self, lead_id: int, updates: Dict) -> bool:
        try:
            datacrazy_id = self._ensure_datacrazy_id(lead_id)
            if not datacrazy_id:
                return False
            
            result = self.crm.update_lead(datacrazy_id, updates)
            if result:
                logger.info(f"✅ Lead {lead_id} atualizado no DataCrazy")
                return True
            
            logger.error(f"❌ Falha ao atualizar lead {lead_id}. updates={updates}")
            return False
        
        except Exception as e:
            logger.exception(f"❌ Erro ao atualizar lead {lead_id}: {e}")
            return False
    
    # -------------------------
    # Stage change
    # -------------------------
    
    def sync_stage_change(self, conversation_id: int) -> bool:
        """
        Sincroniza mudança de estágio da conversa com a pipeline do DataCrazy
        """
        try:
            conversation = self.db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if not conversation:
                logger.error(f"❌ Conversa {conversation_id} não encontrada")
                return False
            
            lead_id = conversation.lead_id
            if not lead_id:
                logger.warning(f"⚠️  Conversa {conversation_id} sem lead_id")
                return False
            
            # Mover o card na pipeline
            new_stage = conversation.current_stage.value
            return self.move_lead_in_pipeline(lead_id, new_stage)
        
        except Exception as e:
            logger.exception(f"❌ Erro ao sincronizar estágio: {e}")
            return False
    
    # -------------------------
    # Add note
    # -------------------------
    
    def add_note_to_lead(self, lead_id: int, note_content: str) -> bool:
        try:
            if not note_content or not note_content.strip():
                logger.warning("⚠️  Nota vazia, ignorando add_note_to_lead")
                return False
            
            datacrazy_id = self._ensure_datacrazy_id(lead_id)
            if not datacrazy_id:
                logger.warning(f"⚠️  Não foi possível garantir datacrazy_id para lead {lead_id}. Nota não enviada.")
                return False
            
            result = self.crm.add_note(datacrazy_id, note_content)
            if result:
                logger.info(f"✅ Nota adicionada ao lead {lead_id} (datacrazy_id={datacrazy_id})")
                return True
            
            logger.error(f"❌ Falha ao adicionar nota no lead {lead_id} (datacrazy_id={datacrazy_id})")
            return False
        
        except Exception as e:
            logger.exception(f"❌ Erro ao adicionar nota: {e}")
            return False
