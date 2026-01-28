# Integração DataCrazy + Z-API + EduFlow

## Arquitetura do Fluxo
```
WhatsApp → Z-API → DataCrazy → Seu Servidor → Z-API (resposta) + DataCrazy (registro)
```

## Como Funciona

1. **Mensagem recebida no WhatsApp**
2. **Z-API** envia webhook para o **DataCrazy** (não para o seu servidor diretamente)
3. **DataCrazy** recebe, cria/atualiza a conversa e dispara a **automação**
4. **Automação** faz POST para `http://44.202.5.137/webhook/datacrazy` com:
   - `name`, `phone`, `message`
   - `conversationId` (ID da conversa no DataCrazy)
   - `leadId` (ID do lead no DataCrazy)
5. **Seu servidor** processa, gera resposta com IA
6. **Resposta enviada via Z-API** (garante entrega no WhatsApp)
7. **Resposta registrada no DataCrazy** (aparece na conversa do CRM)

## Configurações Necessárias

### 1. Z-API (z-api.io)
- Webhook "Ao receber" deve apontar para o **DataCrazy**, não para o seu servidor
- URL: `https://messaging.g1.datacrazy.io/webhooks/z-api/{seu-id}`

### 2. DataCrazy - Conexão Z-API
- Configurações > Conexões > WhatsApp > Z-API
- Preencher: ID da instância, Token, Token de segurança

### 3. DataCrazy - Automação
- Gatilho: "Mensagem recebida" (instância Z-API)
- Ação: POST para `http://44.202.5.137/webhook/datacrazy`
- Body:
```json
{
  "name": "${[Message-1]chatName}",
  "phone": "${[Message-1]phone}",
  "message": "${[Message-1]messageData.text}",
  "conversationId": "${[Message-1]messageData.conversationId}",
  "leadId": "${[Message-1]messageData.contact.id}"
}
```

## Pontos Importantes

### Por que enviar via Z-API e não via DataCrazy?
O endpoint `POST /conversations/{id}/messages` do DataCrazy apenas **registra** a mensagem na conversa, mas **não envia** para o WhatsApp. Por isso:
- Enviamos via Z-API (garante entrega)
- Registramos no DataCrazy (aparece no CRM)

### Código Relevante (message_processor.py)
```python
# 15. ENVIA VIA Z-API (sempre) + registra no DataCrazy
self.zapi.send_text(phone, response)
logger.info(f"✅ Resposta enviada via Z-API para {phone}")

# Registra no DataCrazy para aparecer na conversa
if datacrazy_conversation_id:
    try:
        self.crm.send_message_via_crm(datacrazy_conversation_id, response)
        logger.info(f"📝 Mensagem registrada no DataCrazy")
    except Exception as e:
        logger.warning(f"⚠️  Falha ao registrar no DataCrazy: {e}")
```

## Troubleshooting

### Mensagens não chegam no servidor
- Verificar se automação está ativada no DataCrazy
- Verificar se Z-API aponta para DataCrazy (não para seu servidor)
- Ver logs: `sudo journalctl -u eduagente -f`

### Mensagens não aparecem no WhatsApp
- Verificar logs do Z-API
- Confirmar que está usando `zapi.send_text()` e não só `crm.send_message_via_crm()`

### Mensagens não aparecem no DataCrazy
- Verificar se `conversationId` está sendo passado corretamente
- Verificar se `crm.send_message_via_crm()` retorna sucesso

---
*Documentação criada em: 28/01/2026*
