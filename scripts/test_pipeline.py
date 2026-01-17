"""
Script de teste para movimentação de cards na pipeline do DataCrazy
"""

import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.crm.datacrazy import DataCrazyClient
from app.config import settings
from loguru import logger


def test_pipeline_stages():
    """Testa busca de estágios da pipeline"""
    
    print("\n" + "="*60)
    print("📊 TESTANDO PIPELINE E ESTÁGIOS")
    print("="*60)
    
    client = DataCrazyClient(
        api_token=settings.DATACRAZY_API_TOKEN
    )
    
    # ID da pipeline "IA - Bia"
    pipeline_id = "89e78ad1-2aa9-46d2-b692-28b7e689692b"
    
    try:
        # 1. Buscar estágios da pipeline
        print(f"\n1️⃣ Buscando estágios da pipeline {pipeline_id}...")
        stages = client.get_pipeline_stages(pipeline_id)
        
        print(f"\n✅ Estágios encontrados:")
        print("-" * 40)
        
        stage_map = {}
        for stage in stages:
            name = stage.get("name", "Sem nome")
            stage_id = stage.get("id", "")
            order = stage.get("order", 0)
            stage_map[name] = stage_id
            print(f"  {order}. {name}")
            print(f"     ID: {stage_id}")
        
        print("-" * 40)
        
        # 2. Mostrar mapeamento
        print(f"\n2️⃣ Mapeamento de estágios internos:")
        print("-" * 40)
        
        internal_mapping = {
            "novo": "Entrada do Lead",
            "atendimento": "Em conversa",
            "qualificacao": "Lead Interessado",
            "fechamento": "Fechamento",
        }
        
        for internal, pipeline_name in internal_mapping.items():
            stage_id = stage_map.get(pipeline_name, "NÃO ENCONTRADO")
            status = "✅" if stage_id != "NÃO ENCONTRADO" else "❌"
            print(f"  {status} {internal} → {pipeline_name}")
            if stage_id != "NÃO ENCONTRADO":
                print(f"     ID: {stage_id}")
        
        print("-" * 40)
        
        # 3. Testar busca de deals de um lead (se houver)
        print(f"\n3️⃣ Testando busca de negócios...")
        
        # Busca um lead de teste
        result = client.search_leads(search="558388046720", take=1)
        leads = result.get("data", [])
        
        if leads:
            lead = leads[0]
            lead_id = lead.get("id")
            print(f"   Lead encontrado: {lead.get('name')} (ID: {lead_id})")
            
            # Busca deals do lead
            deals_result = client.list_deals_by_lead(lead_id)
            deals = deals_result.get("data", []) if isinstance(deals_result, dict) else deals_result
            
            if deals:
                print(f"   Negócios encontrados: {len(deals)}")
                for deal in deals:
                    print(f"     - ID: {deal.get('id')}")
                    print(f"       Stage: {deal.get('stageId')}")
            else:
                print("   Nenhum negócio encontrado para este lead")
        else:
            print("   Nenhum lead de teste encontrado")
        
        print("\n" + "="*60)
        print("✅ TESTE CONCLUÍDO")
        print("="*60 + "\n")
        
        return stage_map
        
    except Exception as e:
        print(f"\n❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_move_deal():
    """Testa movimentação de um deal entre estágios"""
    
    print("\n" + "="*60)
    print("🔄 TESTANDO MOVIMENTAÇÃO DE DEAL")
    print("="*60)
    
    client = DataCrazyClient(
        api_token=settings.DATACRAZY_API_TOKEN
    )
    
    try:
        # Busca um lead de teste
        result = client.search_leads(search="558388046720", take=1)
        leads = result.get("data", [])
        
        if not leads:
            print("❌ Nenhum lead de teste encontrado")
            return
        
        lead = leads[0]
        lead_id = lead.get("id")
        print(f"Lead: {lead.get('name')} (ID: {lead_id})")
        
        # Busca deals do lead
        deals_result = client.list_deals_by_lead(lead_id)
        deals = deals_result.get("data", []) if isinstance(deals_result, dict) else deals_result
        
        if not deals:
            print("❌ Nenhum negócio encontrado para este lead")
            return
        
        deal = deals[0]
        deal_id = deal.get("id")
        current_stage = deal.get("stageId")
        
        print(f"Deal ID: {deal_id}")
        print(f"Estágio atual: {current_stage}")
        
        # Busca estágios
        pipeline_id = "89e78ad1-2aa9-46d2-b692-28b7e689692b"
        stages = client.get_pipeline_stages(pipeline_id)
        
        # Encontra o estágio "Em conversa"
        target_stage = None
        for stage in stages:
            if stage.get("name") == "Em conversa":
                target_stage = stage.get("id")
                break
        
        if not target_stage:
            print("❌ Estágio 'Em conversa' não encontrado")
            return
        
        print(f"\nMovendo para 'Em conversa' (ID: {target_stage})...")
        
        # Move o deal
        result = client.move_deal_to_stage(deal_id, target_stage)
        
        print(f"✅ Deal movido com sucesso!")
        print(f"   Resposta: {result}")
        
    except Exception as e:
        print(f"\n❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    stage_map = test_pipeline_stages()
    
    if stage_map:
        resposta = input("\nDeseja testar a movimentação de um deal? (s/n): ")
        if resposta.lower() == "s":
            test_move_deal()
            