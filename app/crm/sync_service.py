from app.crm.datacrazy import DataCrazyClient
from app.crm.stage_mapper import StageMapper
from app.models.lead import Lead
from app.models.conversation import Conversation
from app.database import SessionLocal
from loguru import logger
from typing import Optional, Dict


class CRMSyncService:
    """Serviço de sincronização com DataCrazy CRM"""
    
    def __init__(self):
        self.crm = DataCrazyClient()
        self.db = SessionLocal()
    
    def sync_lead_create(self, lead_id: int) -> bool:
        """
        Cria lead no DataCrazy
        
        Args:
            lead_id: ID do lead no nosso banco
            
        Returns:
            True se criado com sucesso
        """
        
        try:
            # Buscar lead no banco
            lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
            
            if not lead:
                logger.error(f"❌ Lead {lead_id} não encontrado no banco")
                return False
            
            # Se já tem datacrazy_id, não cria novamente
            if lead.datacrazy_id:
                logger.info(f"⏭️  Lead {lead_id} já tem datacrazy_id: {lead.datacrazy_id}")
                return True
            
            # Preparar dados para DataCrazy
            data = {
                "name": lead.name or "Lead sem nome",
                "phone": lead.phone,
                "email": lead.email,
                "origin": lead.origin or "whatsapp"
            }
            
            # Adicionar custom fields do profile
            if lead.profile:
                data["custom_fields"] = lead.profile
            
            # Criar no DataCrazy
            result = self.crm.create_lead(data)
            
            if result and result.get('data'):
                datacrazy_id = result['data'].get('id')
                
                # Salvar datacrazy_id no nosso banco
                lead.datacrazy_id = datacrazy_id
                self.db.commit()
                
                logger.info(f"✅ Lead {lead_id} sincronizado: DataCrazy ID {datacrazy_id}")
                return True
            else:
                logger.error(f"❌ Falha ao criar lead {lead_id} no DataCrazy")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao sincronizar lead {lead_id}: {e}")
            return False
        finally:
            self.db.close()
    
    def sync_lead_update(self, lead_id: int, updates: Dict) -> bool:
        """
        Atualiza lead no DataCrazy
        
        Args:
            lead_id: ID do lead no nosso banco
            updates: Dados para atualizar
            
        Returns:
            True se atualizado com sucesso
        """
        
        try:
            lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
            
            if not lead:
                logger.error(f"❌ Lead {lead_id} não encontrado")
                return False
            
            if not lead.datacrazy_id:
                logger.warning(f"⚠️  Lead {lead_id} sem datacrazy_id, criando...")
                return self.sync_lead_create(lead_id)
            
            # Atualizar no DataCrazy
            result = self.crm.update_lead(lead.datacrazy_id, updates)
            
            if result:
                logger.info(f"✅ Lead {lead_id} atualizado no DataCrazy")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar lead {lead_id}: {e}")
            return False
        finally:
            self.db.close()
    
    def sync_stage_change(self, conversation_id: int) -> bool:
        """
        Sincroniza mudança de estágio da conversa
        
        Args:
            conversation_id: ID da conversa
            
        Returns:
            True se sincronizado com sucesso
        """
        
        try:
            conversation = self.db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if not conversation:
                logger.error(f"❌ Conversa {conversation_id} não encontrada")
                return False
            
            lead = self.db.query(Lead).filter(Lead.id == conversation.lead_id).first()
            
            if not lead or not lead.datacrazy_id:
                logger.warning(f"⚠️  Lead sem datacrazy_id, sincronizando primeiro...")
                self.sync_lead_create(conversation.lead_id)
                # Recarregar lead
                lead = self.db.query(Lead).filter(Lead.id == conversation.lead_id).first()
            
            if not lead or not lead.datacrazy_id:
                return False
            
            # Mapear estágio
            stage_id = StageMapper.map_stage_to_datacrazy(conversation.current_stage.value)
            pipeline_id = StageMapper.get_pipeline_id()
            
            # TODO: Verificar se já existe deal para este lead
            # Por enquanto, vamos assumir que vamos atualizar o lead
            
            update_data = {
                "stage": conversation.current_stage.value,
                "custom_fields": {
                    "stage_interno": conversation.current_stage.value,
                    "status_conversa": conversation.status.value
                }
            }
            
            result = self.crm.update_lead(lead.datacrazy_id, update_data)
            
            if result:
                logger.info(f"✅ Estágio sincronizado: Conversa {conversation_id}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao sincronizar estágio: {e}")
            return False
        finally:
            self.db.close()
    
    def add_note_to_lead(self, lead_id: int, note_content: str) -> bool:
        """
        Adiciona nota ao lead no DataCrazy
        
        Args:
            lead_id: ID do lead no nosso banco
            note_content: Conteúdo da nota
            
        Returns:
            True se nota adicionada
        """
        
        try:
            lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
            
            if not lead or not lead.datacrazy_id:
                logger.warning(f"⚠️  Lead {lead_id} sem datacrazy_id")
                return False
            
            result = self.crm.add_note(lead.datacrazy_id, note_content)
            
            if result:
                logger.info(f"✅ Nota adicionada ao lead {lead_id}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao adicionar nota: {e}")
            return False
        finally:
            self.db.close()