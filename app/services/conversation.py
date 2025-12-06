from app.database import SessionLocal
from app.models.conversation import Conversation, ConversationStatus, ConversationStage
from app.models.message import Message
from app.models.lead import Lead
from typing import Optional, List, Dict
from loguru import logger
from datetime import datetime


class ConversationManager:
    """Gerencia conversas, mensagens e leads"""
    
    def __init__(self):
        self.db = SessionLocal()
    
    def get_or_create_conversation(self, phone: str) -> Conversation:
        """
        Busca conversa existente ou cria nova
        
        Args:
            phone: Número do telefone
            
        Returns:
            Objeto Conversation
        """
        
        # Buscar conversa ativa
        conversation = self.db.query(Conversation).filter(
            Conversation.phone == phone,
            Conversation.status == ConversationStatus.active
        ).first()
        
        if conversation:
            logger.info(f"💬 Conversa existente encontrada: {conversation.id}")
            return conversation
        
        # Buscar ou criar lead
        lead = self.get_or_create_lead(phone)
        
        # Criar nova conversa
        conversation = Conversation(
            phone=phone,
            lead_id=lead.id,
            status=ConversationStatus.active,
            current_stage=ConversationStage.novo
        )
        
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        
        logger.info(f"✅ Nova conversa criada: {conversation.id}")
        
        return conversation
    
    def get_or_create_lead(self, phone: str, name: Optional[str] = None) -> Lead:
        """Busca ou cria lead"""
        
        lead = self.db.query(Lead).filter(Lead.phone == phone).first()
        
        if lead:
            # Atualizar nome se fornecido
            if name and not lead.name:
                lead.name = name
                self.db.commit()
            return lead
        
        # Criar novo lead
        lead = Lead(
            phone=phone,
            name=name,
            origin="whatsapp"
        )
        
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        
        logger.info(f"✅ Novo lead criado: {lead.id}")
        
        return lead
    
    def add_message(self, conversation_id: int, role: str, content: str) -> Message:
        """
        Adiciona mensagem à conversa
        
        Args:
            conversation_id: ID da conversa
            role: 'user' ou 'assistant'
            content: Texto da mensagem
            
        Returns:
            Objeto Message
        """
        
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content
        )
        
        self.db.add(message)
        
        # Atualizar last_message_at da conversa
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if conversation:
            conversation.last_message_at = datetime.now()
        
        self.db.commit()
        self.db.refresh(message)
        
        return message
    
    def get_history(self, conversation_id: int, limit: int = 12) -> List[Dict]:
        """
        Retorna histórico de mensagens
        
        Args:
            conversation_id: ID da conversa
            limit: Quantidade de mensagens (padrão: 12)
            
        Returns:
            Lista de mensagens no formato dict
        """
        
        messages = self.db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.desc()).limit(limit).all()
        
        # Inverter para ordem cronológica
        messages = list(reversed(messages))
        
        # Converter para formato OpenAI
        history = []
        for msg in messages:
            history.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return history
    
    def update_stage(self, conversation_id: int, new_stage: ConversationStage):
        """Atualiza estágio da conversa"""
        
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if conversation:
            old_stage = conversation.current_stage
            conversation.current_stage = new_stage
            self.db.commit()
            
            logger.info(f"📊 Conversa {conversation_id}: {old_stage.value} → {new_stage.value}")
    
    def close(self):
        """Fecha conexão com banco"""
        self.db.close()