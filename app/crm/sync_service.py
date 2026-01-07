from typing import Optional, Dict, Any

from loguru import logger
import requests

from app.config import settings
from app.crm.datacrazy import DataCrazyClient
from app.crm.stage_mapper import StageMapper
from app.models.lead import Lead
from app.models.conversation import Conversation


class CRMSyncService:
    """Serviço de sincronização com DataCrazy CRM"""

    def __init__(self, db):
        self.crm = DataCrazyClient(
            api_token=settings.DATACRAZY_API_TOKEN,
            base_url=settings.DATACRAZY_BASE_URL
        )
        self.db = db

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

            # Recomendado: buscar pelo rawPhone (só números), mas o search costuma aceitar ambos.
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

    # -------------------------
    # Create
    # -------------------------
    def sync_lead_create(self, lead_id: int) -> bool:
        """
        Cria lead no DataCrazy.
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
                return True

            logger.error(f"❌ create_lead retornou sem id. Resposta: {result}")
            return False

        except requests.exceptions.HTTPError as e:
            # Aqui cai quando DataCrazyClient faz raise_for_status() (ex: 400 duplicado)
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

            datacrazy_id = self._ensure_datacrazy_id(lead_id)
            if not datacrazy_id:
                return False

            # Mantive compatível com o seu mapper
            _stage_id = StageMapper.map_stage_to_datacrazy(conversation.current_stage.value)
            _pipeline_id = StageMapper.get_pipeline_id()

            update_data = {
                "stage": conversation.current_stage.value,
                "custom_fields": {
                    "stage_interno": conversation.current_stage.value,
                    "status_conversa": conversation.status.value,
                }
            }

            result = self.crm.update_lead(datacrazy_id, update_data)
            if result:
                logger.info(f"✅ Estágio sincronizado: Conversa {conversation_id}")
                return True

            logger.error(f"❌ Falha ao sincronizar estágio: Conversa {conversation_id}")
            return False

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
