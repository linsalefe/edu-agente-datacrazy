from app.database import SessionLocal
from app.models.conversation import Conversation, ConversationStatus, ConversationStage
from app.models.lead import Lead
from app.models.message import Message
from datetime import datetime

def seed_database():
    """Insere dados de teste no banco de dados"""
    db = SessionLocal()
    
    try:
        print("🌱 Inserindo dados de teste...")
        
        # Criar lead de teste
        lead = Lead(
            phone="+5583999999999",
            name="João Silva",
            email="joao@example.com",
            profile={"interest": "produto_a", "score": 75},
            origin="whatsapp"
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        print(f"✅ Lead criado: {lead.name} (ID: {lead.id})")
        
        # Criar conversa de teste
        conversation = Conversation(
            phone=lead.phone,
            lead_id=lead.id,
            status=ConversationStatus.active,
            current_stage=ConversationStage.atendimento
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        print(f"✅ Conversa criada (ID: {conversation.id})")
        
        # Criar mensagens de teste
        messages = [
            Message(conversation_id=conversation.id, role="user", content="Olá, gostaria de saber mais sobre os produtos"),
            Message(conversation_id=conversation.id, role="assistant", content="Olá João! Claro, temos diversos produtos. Qual seu interesse?"),
            Message(conversation_id=conversation.id, role="user", content="Estou interessado em soluções de CRM")
        ]
        
        for msg in messages:
            db.add(msg)
        
        db.commit()
        print(f"✅ {len(messages)} mensagens criadas")
        
        print("✅ Dados de teste inseridos com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao inserir dados: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()