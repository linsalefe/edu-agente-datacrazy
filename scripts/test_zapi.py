from app.channels.whatsapp.zapi import ZAPIClient
from loguru import logger


def test_zapi_connection():
    """Testa conexão com Z-API"""
    
    print("\n" + "="*60)
    print("📱 TESTANDO CONEXÃO Z-API")
    print("="*60 + "\n")
    
    client = ZAPIClient()
    
    # 1. Verificar status da instância
    print("1️⃣ Verificando status da instância...")
    status = client.get_instance_status()
    
    if status:
        print(f"✅ Status obtido com sucesso")
        print(f"   Conectado: {status.get('connected', False)}")
        print(f"   Telefone: {status.get('phone', 'N/A')}")
    else:
        print("❌ Falha ao obter status")
        return False
    
    # 2. Se conectado, testar envio (para você mesmo)
    if status.get('connected'):
        print("\n2️⃣ Instância conectada!")
        phone = input("Digite seu número com DDI (ex: 5583999999999) para teste: ")
        
        if phone:
            print(f"\n3️⃣ Enviando mensagem de teste para {phone}...")
            success = client.send_text(phone, "🤖 Teste de conexão WhatsApp AI Agent - Funcionando!")
            
            if success:
                print("✅ Mensagem enviada! Verifique seu WhatsApp")
            else:
                print("❌ Falha ao enviar mensagem")
    else:
        print("\n⚠️  Instância NÃO conectada. Escaneie o QR Code no painel Z-API")
    
    print("\n" + "="*60)
    print("✅ TESTE CONCLUÍDO")
    print("="*60 + "\n")


if __name__ == "__main__":
    test_zapi_connection()