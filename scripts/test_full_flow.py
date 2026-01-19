"""
Script de Teste - Fluxo Completo
Testa: Movimentação de pipeline + Notas no CRM

Execute: python scripts/test_full_flow.py
"""

import sys
import os
import asyncio

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.services.message_processor import MessageProcessor
from app.models.conversation import Conversation, ConversationStatus
from app.models.lead import Lead
from loguru import logger


async def simulate_conversation():
    """Simula uma conversa completa para testar o fluxo"""
    
    print("\n" + "="*70)
    print("🧪 TESTE DE FLUXO COMPLETO")
    print("   - Movimentação automática de pipeline")
    print("   - Notas inteligentes no CRM")
    print("="*70)
    
    db = SessionLocal()
    
    # Número de teste (use um número real para ver no DataCrazy)
    # Ou use um número fictício para teste local
    TEST_PHONE = input("\n📱 Digite o número de teste (com DDI, ex: 5583999999999): ").strip()
    
    if not TEST_PHONE:
        TEST_PHONE = "5500000000000"  # Número fictício
        print(f"   Usando número fictício: {TEST_PHONE}")
    
    try:
        processor = MessageProcessor(db)
        
        # Limpa conversa anterior de teste (se existir)
        old_conv = db.query(Conversation).filter(
            Conversation.phone == TEST_PHONE,
            Conversation.status == ConversationStatus.active
        ).first()
        
        if old_conv:
            print(f"\n🗑️  Limpando conversa anterior (ID: {old_conv.id})...")
            old_conv.status = ConversationStatus.closed
            db.commit()
        
        # ==========================================
        # SIMULAÇÃO DA CONVERSA
        # ==========================================
        
        mensagens = [
            # Estágio: NOVO → ATENDIMENTO
            ("Olá, quero saber sobre os cursos", "Primeiro contato"),
            
            # Coleta curso e cidade
            ("Tenho interesse em Administração", "Informa curso"),
            ("Sou de Arcos", "Informa cidade"),
            
            # Estágio: ATENDIMENTO → QUALIFICAÇÃO
            ("Sim, já terminei o ensino médio", "Confirma escolaridade"),
            
            # Coleta motivação
            ("Quero crescer na minha carreira e conseguir uma promoção na empresa", "Informa motivação"),
            
            # Estágio: QUALIFICAÇÃO → FECHAMENTO
            ("Meu nome é João Carlos Silva", "Informa nome completo"),
            
            # Coleta dados de matrícula
            ("Meu CPF é 123.456.789-00", "Informa CPF"),
            ("Meu e-mail é joao.silva@email.com", "Informa e-mail"),
            ("Nasci em 15/03/1990", "Informa data nascimento"),
            ("Meu CEP é 35588-000", "Informa CEP"),
        ]
        
        print("\n" + "-"*70)
        print("📝 INICIANDO SIMULAÇÃO DE CONVERSA")
        print("-"*70)
        
        for i, (msg, descricao) in enumerate(mensagens, 1):
            print(f"\n{'='*70}")
            print(f"📨 MENSAGEM {i}/{len(mensagens)}: {descricao}")
            print(f"{'='*70}")
            print(f"👤 Lead: {msg}")
            print("-"*70)
            
            # Processa a mensagem
            await processor.process_message(
                phone=TEST_PHONE,
                text=msg,
                name="Lead Teste"
            )
            
            # Mostra status atual
            conv = db.query(Conversation).filter(
                Conversation.phone == TEST_PHONE,
                Conversation.status == ConversationStatus.active
            ).first()
            
            if conv:
                lead = db.query(Lead).filter(Lead.id == conv.lead_id).first()
                
                print(f"\n📊 STATUS ATUAL:")
                print(f"   Estágio: {conv.current_stage.value}")
                print(f"   Lead ID: {lead.id if lead else 'N/A'}")
                print(f"   DataCrazy ID: {lead.datacrazy_id if lead else 'N/A'}")
                
                if lead and lead.profile:
                    qual = lead.profile.get("qualification", {})
                    print(f"\n   📋 Dados coletados:")
                    for key, value in qual.items():
                        if value:
                            print(f"      • {key}: {value}")
            
            # Pausa para ver o resultado
            input("\n⏸️  Pressione ENTER para continuar...")
        
        # ==========================================
        # RESUMO FINAL
        # ==========================================
        
        print("\n" + "="*70)
        print("✅ SIMULAÇÃO CONCLUÍDA!")
        print("="*70)
        
        conv = db.query(Conversation).filter(
            Conversation.phone == TEST_PHONE,
            Conversation.status == ConversationStatus.active
        ).first()
        
        if conv:
            lead = db.query(Lead).filter(Lead.id == conv.lead_id).first()
            
            print(f"""
📊 RESULTADO FINAL:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 Estágio final: {conv.current_stage.value}
👤 Nome: {lead.name if lead else 'N/A'}
📱 Telefone: {TEST_PHONE}
🔗 DataCrazy ID: {lead.datacrazy_id if lead else 'N/A'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 VERIFIQUE NO DATACRAZY:
1. Acesse o lead no CRM
2. Veja se o card está no estágio "Fechamento"
3. Confira as notas criadas automaticamente

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            """)
        
    except Exception as e:
        logger.error(f"❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


def test_pipeline_movement_only():
    """Testa apenas a movimentação da pipeline (sem simular conversa)"""
    
    print("\n" + "="*70)
    print("🧪 TESTE RÁPIDO - MOVIMENTAÇÃO DE PIPELINE")
    print("="*70)
    
    db = SessionLocal()
    
    try:
        from app.crm.sync_service import CRMSyncService
        
        crm = CRMSyncService(db)
        
        # Busca um lead existente
        lead = db.query(Lead).filter(Lead.datacrazy_id.isnot(None)).first()
        
        if not lead:
            print("❌ Nenhum lead com datacrazy_id encontrado")
            return
        
        print(f"\n📋 Lead encontrado: {lead.name} (ID: {lead.id})")
        print(f"   DataCrazy ID: {lead.datacrazy_id}")
        
        # Testa movimentação
        stages = ["atendimento", "qualificacao", "fechamento"]
        
        for stage in stages:
            input(f"\n⏸️  Pressione ENTER para mover para '{stage}'...")
            
            result = crm.move_lead_in_pipeline(lead.id, stage)
            
            if result:
                print(f"✅ Movido para: {stage}")
            else:
                print(f"❌ Falha ao mover para: {stage}")
        
        print("\n✅ Teste concluído! Verifique no DataCrazy.")
        
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


def test_add_note():
    """Testa apenas adicionar uma nota"""
    
    print("\n" + "="*70)
    print("🧪 TESTE RÁPIDO - ADICIONAR NOTA")
    print("="*70)
    
    db = SessionLocal()
    
    try:
        from app.crm.sync_service import CRMSyncService
        
        crm = CRMSyncService(db)
        
        # Busca um lead existente
        lead = db.query(Lead).filter(Lead.datacrazy_id.isnot(None)).first()
        
        if not lead:
            print("❌ Nenhum lead com datacrazy_id encontrado")
            return
        
        print(f"\n📋 Lead encontrado: {lead.name} (ID: {lead.id})")
        print(f"   DataCrazy ID: {lead.datacrazy_id}")
        
        # Adiciona nota de teste
        nota = """
🧪 NOTA DE TESTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Esta é uma nota de teste do sistema.
Criada automaticamente pelo bot Bia.

📅 Data: Agora
✅ Status: Funcionando!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """.strip()
        
        result = crm.add_note_to_lead(lead.id, nota)
        
        if result:
            print("\n✅ Nota adicionada com sucesso!")
            print("   Verifique no DataCrazy.")
        else:
            print("\n❌ Falha ao adicionar nota")
        
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


if __name__ == "__main__":
    print("\n" + "="*70)
    print("🧪 MENU DE TESTES")
    print("="*70)
    print("""
1. Simular conversa completa (recomendado)
   - Cria lead, avança estágios, adiciona notas

2. Testar movimentação de pipeline
   - Move um lead existente entre estágios

3. Testar adicionar nota
   - Adiciona uma nota de teste a um lead

0. Sair
    """)
    
    opcao = input("Escolha uma opção: ").strip()
    
    if opcao == "1":
        asyncio.run(simulate_conversation())
    elif opcao == "2":
        test_pipeline_movement_only()
    elif opcao == "3":
        test_add_note()
    else:
        print("👋 Saindo...")