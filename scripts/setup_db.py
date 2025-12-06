from app.database import Base, engine
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.lead import Lead
from app.models.followup import Followup
from app.models.metric import Metric

def setup_database():
    """Cria todas as tabelas no banco de dados"""
    try:
        print("🔧 Criando tabelas no banco de dados...")
        Base.metadata.create_all(bind=engine)
        print("✅ Tabelas criadas com sucesso!")
        return True
    except Exception as e:
        print(f"❌ Erro ao criar tabelas: {e}")
        return False

if __name__ == "__main__":
    setup_database()