from app.database import Base, engine, SessionLocal
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.lead import Lead
from app.models.followup import Followup
from app.models.metric import Metric

def reset_database():
    """CUIDADO: Deleta todas as tabelas e recria (apenas para desenvolvimento)"""
    
    response = input("⚠️  ATENÇÃO: Isso vai deletar TODOS os dados! Confirma? (sim/não): ")
    
    if response.lower() != "sim":
        print("❌ Operação cancelada.")
        return False
    
    try:
        print("🗑️  Deletando todas as tabelas...")
        Base.metadata.drop_all(bind=engine)
        print("✅ Tabelas deletadas!")
        
        print("🔧 Recriando tabelas...")
        Base.metadata.create_all(bind=engine)
        print("✅ Tabelas recriadas com sucesso!")
        
        return True
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

if __name__ == "__main__":
    reset_database()