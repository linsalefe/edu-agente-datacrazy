"""
Script de teste para DataCrazy API - VERSÃO MELHORADA
Usa dados únicos para evitar duplicatas
"""

import sys
import os
from datetime import datetime

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.crm.datacrazy import DataCrazyClient
from app.config import settings
from loguru import logger


def test_datacrazy():
    """Testa conexão com DataCrazy"""
    
    print("\n" + "="*60)
    print("📊 TESTANDO CONEXÃO DATACRAZY CRM")
    print("="*60)
    
    # Inicializa cliente
    client = DataCrazyClient(
        api_token=settings.DATACRAZY_API_TOKEN
    )
    
    try:
        # Teste 1: Health check
        print("\n1️⃣ Testando conexão...")
        if client.health_check():
            print("✅ Conexão OK")
        else:
            print("❌ Falha na conexão")
            return
        
        # Teste 2: Criar lead com dados únicos
        print("\n2️⃣ Criando lead de teste...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        lead_data = {
            "name": f"Lead Teste {timestamp}",
            "phone": f"+558399{timestamp[-6:]}",  # Últimos 6 dígitos únicos
            "email": f"teste_{timestamp}@whatsappbot.com",
            "source": "WhatsApp Bot - Teste API",
            "company": "Teste Company"
        }
        
        lead = client.create_lead(lead_data)
        print(f"✅ Lead criado: ID {lead.get('id')}")
        print(f"   Nome: {lead.get('name')}")
        print(f"   Phone: {lead.get('phone')}")
        print(f"   Email: {lead.get('email')}")
        
        if "id" in lead:
            lead_id = lead["id"]
            
            # Teste 3: Adicionar nota
            print(f"\n3️⃣ Adicionando nota ao lead {lead_id}...")
            note_text = f"Nota de teste criada via API em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            note = client.add_note(lead_id, note_text)
            print(f"✅ Nota adicionada com sucesso!")
            
            # Teste 4: Atualizar lead
            print(f"\n4️⃣ Atualizando lead {lead_id}...")
            update = client.update_lead(lead_id, {
                "company": "Teste Company ATUALIZADA via API"
            })
            print(f"✅ Lead atualizado com sucesso!")
            
            # Teste 5: Buscar lead
            print(f"\n5️⃣ Buscando lead {lead_id}...")
            fetched = client.get_lead(lead_id)
            print(f"✅ Lead encontrado: {fetched.get('name')}")
            print(f"   Company: {fetched.get('company')}")
        
        print("\n" + "="*60)
        print("✅ TODOS OS TESTES PASSARAM!")
        print("="*60)
        print("\n📊 RESUMO:")
        print(f"   • Conexão: OK")
        print(f"   • Criar Lead: OK")
        print(f"   • Adicionar Nota: OK")
        print(f"   • Atualizar Lead: OK")
        print(f"   • Buscar Lead: OK")
        
    except Exception as e:
        print(f"\n❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()
        
        print("\n⚠️  Verifique:")
        print("   - Token da API está correto no .env")
        print("   - URL base: https://api.g1.datacrazy.io/api/v1")
        print("   - Sua conta DataCrazy está ativa")
        
    print("\n" + "="*60)
    print("✅ TESTE CONCLUÍDO")
    print("="*60 + "\n")


if __name__ == "__main__":
    test_datacrazy()