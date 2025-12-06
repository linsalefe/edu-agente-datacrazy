import os
import sys

# Garante que a raiz do projeto (whatsapp-ai-agent) está no sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.database import engine
from app.config import settings


def test_database():
    try:
        conn = engine.connect()
        print("✅ Conexão com PostgreSQL OK")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Erro ao conectar PostgreSQL: {e}")
        return False


if __name__ == "__main__":
    print(f"Testando conexão com: {settings.DATABASE_URL}")
    test_database()
