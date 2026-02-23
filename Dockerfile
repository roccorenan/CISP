# ─────────────────────────────────────────────────────────────
#  STAGE 1 — instala dependências
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt waitress


# ─────────────────────────────────────────────────────────────
#  STAGE 2 — imagem final enxuta
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/roccorenan/CISP"
LABEL description="Portal CISP - Consulta de Crédito"

WORKDIR /app

# Copia pacotes do stage anterior
COPY --from=builder /install /usr/local

# Copia o código da aplicação
# (.dockerignore garante que .env, .git, data.json etc. NÃO entrem)
COPY . .

# Usuário não-root por segurança
RUN useradd -r -s /bin/false appuser \
 && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

# Waitress: servidor WSGI de produção (sem o debug server do Flask)
CMD ["python", "-m", "waitress", "--listen=0.0.0.0:5000", "--threads=4", "app:app"]
