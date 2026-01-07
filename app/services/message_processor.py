"""
Processador de Mensagens
Orquestra todo o fluxo de processamento de mensagens
"""

from datetime import datetime
from sqlalchemy.orm import Session
from loguru import logger

from app.models.conversation import Conversation, ConversationStatus, ConversationStage
from app.models.message import Message
from app.models.lead import Lead
from app.rag.query import RAGQuery
from app.llm.response_generator import ResponseGenerator
from app.channels.whatsapp.zapi import ZAPIClient
from app.crm.sync_service import CRMSyncService
from app.core.scheduler import FollowupScheduler
from app.services.handoff import HandoffService
from app.config import settings


class MessageProcessor:
    """Processa mensagens do WhatsApp e orquestra respostas da IA"""
    
    def __init__(self, db: Session):
        self.db = db
        self.zapi = ZAPIClient()
        self.crm = CRMSyncService(db)
        self.response_gen = ResponseGenerator()
    
    async def process_message(self, phone: str, text: str, name: str = None):
        """
        Processa uma mensagem recebida
        
        Args:
            phone: Telefone do cliente
            text: Texto da mensagem
            name: Nome do cliente (opcional)
        """
        logger.info(f"📱 Processando mensagem de {phone}")
        
        try:
            # 1. Get/Create Conversation
            conversation = self._get_or_create_conversation(phone, name)
            
            # 2. Verifica se está em handoff
            if conversation.status == ConversationStatus.handoff:
                logger.info(f"⚠️  Conversa {conversation.id} está em handoff - ignorando")
                return
            
            # 3. Salva mensagem do usuário
            user_message = Message(
                conversation_id=conversation.id,
                role="user",
                content=text
            )
            self.db.add(user_message)
            self.db.commit()
            
            # 4. Atualiza timestamp da conversa
            conversation.last_message_at = datetime.utcnow()
            self.db.commit()
            
            # 5. Busca contexto RAG
            rag_query = RAGQuery()
            context = rag_query.build_context(text, top_k=4)
            logger.info(f"📚 Contexto RAG obtido: {len(context)} caracteres")
            
            # 6. Busca histórico da conversa
            history = self._get_conversation_history(conversation.id, limit=10)
            
            # 7. Gera resposta da IA
            response, needs_handoff = self.response_gen.generate_response(
                user_message=text,
                history=history,
                stage=conversation.current_stage.value,
                lead_data=conversation.lead.to_dict() if conversation.lead else {},
                context=context
            )
            
            logger.info(f"🤖 Resposta gerada: {response[:100]}...")
            logger.info(f"🤝 Necessita handoff: {needs_handoff}")
            
            # 8. Verifica se precisa de handoff
            if needs_handoff:
                HandoffService.request_handoff(
                    conversation_id=conversation.id,
                    reason="IA solicitou transferência para humano",
                    db=self.db
                )
                return
            
            # 9. Salva resposta da IA
            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=response
            )
            self.db.add(assistant_message)
            self.db.commit()
            
            # 10. Envia resposta via WhatsApp
            self.zapi.send_text(phone, response)
            logger.info(f"✅ Resposta enviada para {phone}")
            
            # 11. Sincroniza com CRM (async)
            try:
                # Adiciona nota da interação
                if conversation.lead:
                    self.crm.add_note_to_lead(
                        conversation.lead_id,
                        f"💬 CONVERSA\n\nCliente: {text}\n\nIA: {response}"
                    )
            except Exception as e:
                logger.warning(f"⚠️  Erro ao sincronizar com CRM: {e}")
            
            # 12. Agenda follow-ups (apenas para novas conversas)
            messages_count = self.db.query(Message).filter(
                Message.conversation_id == conversation.id
            ).count()
            
            if messages_count == 2:  # primeira interação (user + assistant)
                # Agenda follow-ups automáticos
                FollowupScheduler.schedule_followups(conversation.id, self.db)
                logger.info(f"📅 Follow-ups agendados para conversa {conversation.id}")
            
            logger.info(f"✅ Mensagem processada com sucesso")
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar mensagem: {e}")
            raise
    
    def _get_or_create_conversation(self, phone: str, name: str = None):
        """Busca ou cria uma conversa"""
        # Busca conversa ativa
        conversation = self.db.query(Conversation).filter(
            Conversation.phone == phone,
            Conversation.status == ConversationStatus.active
        ).first()
        
        if conversation:
            logger.info(f"📖 Conversa existente encontrada: {conversation.id}")
            return conversation
        
        # Cria nova conversa
        logger.info(f"🆕 Criando nova conversa para {phone}")
        
        # Get/Create Lead
        lead = self._get_or_create_lead(phone, name)
        
        conversation = Conversation(
            phone=phone,
            lead_id=lead.id,
            status=ConversationStatus.active,
            current_stage=ConversationStage.novo,
            last_message_at=datetime.utcnow()
        )
        
        self.db.add(conversation)
        self.db.commit()
        
        logger.info(f"✅ Conversa criada: {conversation.id}")
        
        # Sincroniza lead com CRM
        try:
            self.crm.sync_lead(lead.id)
        except Exception as e:
            logger.warning(f"⚠️  Erro ao sincronizar lead com CRM: {e}")
        
        return conversation
    
    def _get_or_create_lead(self, phone: str, name: str = None):
        """Busca ou cria um lead"""
        lead = self.db.query(Lead).filter(Lead.phone == phone).first()
        
        if lead:
            logger.info(f"📖 Lead existente: {lead.id}")
            return lead
        
        # Cria novo lead
        lead = Lead(
            phone=phone,
            name=name or "Cliente",
            origin="whatsapp"
        )
        
        self.db.add(lead)
        self.db.commit()
        
        logger.info(f"✅ Lead criado: {lead.id}")
        return lead
    
    def _get_conversation_history(self, conversation_id: int, limit: int = 10):
        """Busca histórico de mensagens"""
        messages = self.db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.desc()).limit(limit).all()
        
        # Inverte ordem (mais antigas primeiro)
        messages.reverse()
        
        history = []
        for msg in messages:
            history.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return history