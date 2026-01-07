# Stage 1: Build
FROM python:3.11-slim as builder

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependências
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Instalar apenas dependências de runtime
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar dependências do builder
COPY --from=builder /root/.local /root/.local

# Copiar código da aplicação
COPY . .

# Adicionar ao PATH
ENV PATH=/root/.local/bin:$PATH

# Criar usuário não-root
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expor porta
EXPOSE 8000

# Comando padrão
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]