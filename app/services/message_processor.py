from app.utils.dedup import DedupManager
from app.utils.anti_loop import AntiLoopManager
from app.services.conversation import ConversationManager
from app.llm.response_generator import ResponseGenerator
from app.channels.whatsapp.zapi import ZAPIClient
from app.crm.sync_service import CRMSyncService
from app.models.lead import Lead
from loguru import logger
from typing import Optional


class MessageProcessor:
    """Processa mensagens do WhatsApp end-to-end"""
    
    def __init__(self):
        self.dedup = DedupManager()
        self.anti_loop = AntiLoopManager()
        self.conv_manager = ConversationManager()
        self.response_gen = ResponseGenerator()
        self.whatsapp = ZAPIClient()
        self.crm_sync = CRMSyncService()
    
    def process_message(self, phone: str, text: str, name: Optional[str] = None) -> bool:
        """
        Processa mensagem completa: recebe, gera resposta, envia
        
        Args:
            phone: Número do telefone
            text: Texto da mensagem
            name: Nome do remetente (opcional)
            
        Returns:
            True se processado com sucesso
        """
        
        try:
            # 1. Verificar duplicata
            if self.dedup.is_duplicate(phone, text):
                logger.info("⏭️  Mensagem duplicada - ignorada")
                return False
            
            # 2. Verificar loop
            if self.anti_loop.is_loop(phone, text):
                logger.info("🔄 Loop detectado - ignorada")
                return False
            
            # 3. Get/Create conversa
            conversation = self.conv_manager.get_or_create_conversation(phone)
            
            # Atualizar nome do lead se fornecido
            if name:
                lead = self.conv_manager.get_or_create_lead(phone, name)
            
            # 4. Salvar mensagem do usuário
            self.conv_manager.add_message(
                conversation_id=conversation.id,
                role="user",
                content=text
            )
            
            # 5. Buscar histórico
            history = self.conv_manager.get_history(conversation.id, limit=12)
            
            # 6. Preparar dados do lead
            lead_data = None
            if conversation.lead_id:
                lead = self.conv_manager.db.query(Lead).filter(
                    Lead.id == conversation.lead_id
                ).first()
                
                if lead:
                    lead_data = {
                        'name': lead.name,
                        'phone': lead.phone,
                        'email': lead.email,
                        'profile': lead.profile or {}
                    }
            
            # 7. Gerar resposta com IA
            logger.info(f"🤖 Gerando resposta para: {text[:50]}...")
            
            response, precisa_handoff = self.response_gen.generate_response(
                user_message=text,
                conversation_history=history,
                stage=conversation.current_stage.value,
                lead_data=lead_data
            )
            
            if not response:
                logger.error("❌ Falha ao gerar resposta")
                response = "Desculpe, estou com dificuldades técnicas. Um atendente vai te responder em breve."
            
            # 8. Enviar resposta via WhatsApp
            success = self.whatsapp.send_text(phone, response)
            
            if not success:
                logger.error(f"❌ Falha ao enviar mensagem para {phone}")
                return False
            
            # 9. Registrar para anti-loop
            self.anti_loop.register_sent_message(phone, response)
            
            # 10. Salvar resposta do assistente
            self.conv_manager.add_message(
                conversation_id=conversation.id,
                role="assistant",
                content=response
            )
            
            # 11. Sincronizar com DataCrazy (async, não trava)
            try:
                # Se é primeira mensagem, criar lead no CRM
                if len(history) <= 2:  # Apenas user + assistant
                    logger.info(f"📤 Sincronizando novo lead com DataCrazy...")
                    self.crm_sync.sync_lead_create(conversation.lead_id)
                
                # Adicionar nota com a conversa
                note = f"WhatsApp - {name or 'Cliente'}: {text}\nBot: {response}"
                self.crm_sync.add_note_to_lead(conversation.lead_id, note)
                
            except Exception as crm_error:
                # Não deixar erro do CRM quebrar o fluxo
                logger.error(f"⚠️  Erro ao sincronizar CRM (não crítico): {crm_error}")
            
            # 12. Tratar handoff se necessário
            if precisa_handoff:
                logger.warning(f"⚠️  Handoff necessário para conversa {conversation.id}")
                # Adicionar nota de handoff
                try:
                    self.crm_sync.add_note_to_lead(
                        conversation.lead_id,
                        "🚨 HANDOFF SOLICITADO - Cliente precisa de atendimento humano"
                    )
                except:
                    pass
            
            logger.info(f"✅ Mensagem processada com sucesso: {phone}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar mensagem: {e}")
            return False
        
        finally:
            self.conv_manager.close()