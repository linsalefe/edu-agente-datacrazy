from app.llm.response_generator import ResponseGenerator
from loguru import logger


def test_llm_responses():
    """Testa geração de respostas em diferentes estágios"""
    
    generator = ResponseGenerator()
    
    print("\n" + "="*70)
    print("🤖 TESTANDO SISTEMA DE RESPOSTAS LLM")
    print("="*70 + "\n")
    
    # Cenário 1: Primeiro contato
    print("\n📌 CENÁRIO 1: PRIMEIRO CONTATO (Atendimento)")
    print("-" * 70)
    
    response, handoff = generator.generate_response(
        user_message="Olá, gostaria de saber sobre os cursos",
        conversation_history=[],
        stage="atendimento",
        lead_data=None
    )
    
    print(f"👤 User: Olá, gostaria de saber sobre os cursos")
    print(f"🤖 Bot: {response}")
    print(f"🔄 Handoff: {handoff}")
    
    # Cenário 2: Interesse em curso específico
    print("\n📌 CENÁRIO 2: QUALIFICAÇÃO")
    print("-" * 70)
    
    history = [
        {"role": "user", "content": "Olá, gostaria de saber sobre os cursos"},
        {"role": "assistant", "content": response}
    ]
    
    response2, handoff2 = generator.generate_response(
        user_message="Tenho interesse em Administração",
        conversation_history=history,
        stage="qualificacao",
        lead_data={"name": "João", "phone": "+5583999999999"}
    )
    
    print(f"👤 User: Tenho interesse em Administração")
    print(f"🤖 Bot: {response2}")
    print(f"🔄 Handoff: {handoff2}")
    
    # Cenário 3: Objeção de preço
    print("\n📌 CENÁRIO 3: OBJEÇÃO DE PREÇO")
    print("-" * 70)
    
    history.extend([
        {"role": "user", "content": "Tenho interesse em Administração"},
        {"role": "assistant", "content": response2}
    ])
    
    response3, handoff3 = generator.generate_response(
        user_message="Parece caro, não sei se consigo pagar",
        conversation_history=history,
        stage="qualificacao",
        intent="objecao"
    )
    
    print(f"👤 User: Parece caro, não sei se consigo pagar")
    print(f"🤖 Bot: {response3}")
    print(f"🔄 Handoff: {handoff3}")
    
    print("\n" + "="*70)
    print("✅ TESTE CONCLUÍDO")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_llm_responses()