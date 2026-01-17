# 🤖 WhatsApp AI Agent - Bia (UNOPAR/Anhanguera)

Agente de vendas inteligente para WhatsApp, integrado ao DataCrazy CRM. A **Bia** é uma consultora educacional virtual que qualifica leads e realiza pré-matrículas de forma humanizada.

## ✨ Funcionalidades

- 🗣️ **Atendimento humanizado** - Conversa natural, não robótica
- 📊 **Qualificação automática** - Coleta dados gradualmente durante a conversa
- 🎯 **Funil de vendas** - Estágios: Atendimento → Qualificação → Fechamento
- 🔄 **Integração CRM** - Sincroniza leads e conversas com DataCrazy
- 📚 **RAG (Knowledge Base)** - Base de conhecimento sobre cursos UNOPAR
- ⏰ **Follow-ups automáticos** - Reengaja leads que pararam de responder
- 🏷️ **Controle de pausa** - Tag `IA_PAUSADA` no CRM desativa o bot

## 🚀 Stack

| Componente | Tecnologia |
|------------|------------|
| Backend | FastAPI + Python 3.11 |
| Database | PostgreSQL 16 + pgvector |
| Cache | Redis |
| AI/LLM | OpenAI GPT-4o-mini |
| RAG | pgvector + text-embedding-3-small |
| WhatsApp | Z-API |
| CRM | DataCrazy |
| Workers | Celery + Celery Beat |
| Container | Docker + Docker Compose |

## 📁 Estrutura do Projeto

```
whatsapp-ai-agent/
├── app/
│   ├── channels/whatsapp/    # Integração Z-API
│   ├── crm/                  # Integração DataCrazy
│   ├── llm/                  # OpenAI + Prompts
│   │   └── prompts/          # Prompts por estágio
│   ├── models/               # SQLAlchemy models
│   ├── rag/                  # Sistema RAG
│   ├── services/             # Lógica de negócio
│   ├── utils/                # Utilitários
│   └── workers/              # Celery tasks
├── data/rag/cursos/          # Base de conhecimento
├── scripts/                  # Scripts utilitários
├── alembic/                  # Migrações DB
└── docker-compose.yml
```

## ⚙️ Instalação

### Pré-requisitos

- Python 3.11+
- PostgreSQL 16 com pgvector
- Redis
- Docker + Docker Compose (opcional)

### Setup Local

1. **Clone o repositório**
```bash
git clone <repo-url>
cd whatsapp-ai-agent
```

2. **Crie o ambiente virtual**
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate     # Windows
```

3. **Instale as dependências**
```bash
pip install -r requirements.txt
```

4. **Configure as variáveis de ambiente**
```bash
cp .env.example .env
# Edite o .env com suas credenciais
```

5. **Execute as migrações**
```bash
alembic upgrade head
```

6. **Carregue a base de conhecimento RAG**
```bash
python scripts/load_rag.py
```

7. **Inicie o servidor**
```bash
uvicorn app.main:app --reload
```

### Setup com Docker

```bash
docker-compose up -d
```

## 🔑 Variáveis de Ambiente

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/whatsapp_agent

# Redis
REDIS_URL=redis://localhost:6379/0

# OpenAI
OPENAI_API_KEY=sk-...

# Z-API (WhatsApp)
ZAPI_TOKEN=seu_token
ZAPI_INSTANCE=sua_instancia
ZAPI_CLIENT_TOKEN=seu_client_token

# DataCrazy CRM
DATACRAZY_API_TOKEN=seu_token
DATACRAZY_BASE_URL=https://api.g1.datacrazy.io/api/v1
```

## 🎭 A Bia - Personalidade do Bot

A Bia é uma consultora educacional simpática e acolhedora que:

- ✅ Reage às respostas antes de fazer novas perguntas
- ✅ Usa linguagem natural de WhatsApp
- ✅ Demonstra empatia genuína
- ✅ Celebra as decisões do lead
- ✅ Coleta dados de forma gradual e natural

### Exemplos de conversa:

**Robótico (como era):**
> "Qual curso te interessa?"
> "Administração"
> "Você já concluiu o ensino médio?"

**Humanizado (como é agora):**
> "Qual curso te interessa?"
> "Administração"
> "Administração é excelente! Muita gente busca esse curso pra crescer na carreira. Você já trabalha na área? 😊"

## 📊 Fluxo de Vendas

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ ATENDIMENTO │ ──▶ │ QUALIFICAÇÃO │ ──▶ │ FECHAMENTO  │
└─────────────┘     └──────────────┘     └─────────────┘
     │                    │                    │
     ▼                    ▼                    ▼
  • Curso             • Motivação          • CPF
  • Cidade            • Escolaridade       • E-mail
                                           • Data nasc.
                                           • CEP
```

## 🔌 Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/` | Status da aplicação |
| GET | `/health` | Health check básico |
| GET | `/health/detailed` | Health check com dependências |
| GET | `/metrics` | Métricas Prometheus |
| POST | `/webhook` | Recebe webhooks do Z-API |

## 🧪 Scripts Úteis

```bash
# Testar conexões
python scripts/test_connections.py

# Testar Z-API
python scripts/test_zapi.py

# Testar DataCrazy
python scripts/test_datacrazy.py

# Testar RAG
python scripts/test_rag.py

# Testar LLM
python scripts/test_llm.py

# Carregar base RAG
python scripts/load_rag.py

# Reset do banco (CUIDADO!)
python scripts/reset_db.py
```

## 📚 Base de Conhecimento (RAG)

Os arquivos de conhecimento ficam em `data/rag/cursos/`:

- `cursos-tecnologia.txt` - Cursos de TI
- `cursos-saude.txt` - Cursos de Saúde
- `cursos-gestao.txt` - Cursos de Gestão
- `cursos-licenciaturas.txt` - Licenciaturas
- `cursos-engenharia.txt` - Engenharias
- `cursos-diversos.txt` - Outros cursos

## 🏷️ Controle via CRM

### Pausar a IA para um lead:
Adicione a tag `IA_PAUSADA` no lead do DataCrazy. O bot irá ignorar mensagens desse lead.

### Retomar atendimento automático:
Remova a tag `IA_PAUSADA` do lead.

## 📈 Métricas e Monitoramento

- Endpoint `/metrics` no formato Prometheus
- Logs estruturados com Loguru em `logs/`
- Health checks para todas as dependências

## 🤝 Handoff para Humano

O bot transfere automaticamente quando:
- Lead pede para falar com atendente
- Situação financeira complexa
- Dúvidas muito específicas
- Lead demonstra insatisfação

## 📝 Changelog

### v1.1.0 (2025-01-16)
- ✨ Nova personalidade humanizada (Bia)
- 🐛 Fix: Não repete perguntas de dados já coletados
- 🐛 Fix: Removido pedido de endereço (só CEP)
- 📝 Prompts reescritos com tom empático

### v1.0.0 (2025-12-06)
- 🎉 Versão inicial
- Integração Z-API
- Integração DataCrazy
- Sistema RAG
- Follow-ups automáticos

---

**Desenvolvido por:** Álefe  
**Versão:** 1.1.0