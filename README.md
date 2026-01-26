# 🤖 WhatsApp AI Agent - DataCrazy Integration

Agente de vendas WhatsApp com IA, integrado ao DataCrazy CRM.

## 🚀 Stack

- **Backend**: FastAPI + Python 3.11+
- **Database**: PostgreSQL 16 + Redis
- **AI**: OpenAI GPT + RAG (pgvector)
- **WhatsApp**: Z-API
- **CRM**: DataCrazy
- **Workers**: Celery + Celery Beat

## ⚙️ Instalação

### Pré-requisitos

- Python 3.11+
- PostgreSQL 16
- Redis
- Docker + Docker Compose

### Setup

1. Clone o repositório
2. Copie `.env.example` para `.env` e configure as variáveis
3. Crie o ambiente virtual:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows
```

4. Instale as dependências:
```bash
pip install -r requirements.txt
```

5. Rode o servidor:
```bash
uvicorn app.main:app --reload
```

6. Acesse: `http://localhost:8000`

## 📚 Documentação

- Setup completo: `docs/setup.md`
- API Reference: `http://localhost:8000/docs`

## 🔑 Variáveis de Ambiente

Veja `.env.example` para todas as variáveis obrigatórias.

## 📊 Status do Projeto

**Sprint atual**: Sprint 0 - Setup Inicial ✅

---

**Versão**: 1.0.0  
**Desenvolvido por**: Élefe