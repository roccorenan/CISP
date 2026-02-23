#!/bin/bash
# =================================================================
#  setup-servidor.sh
#  Execute UMA VEZ no servidor Linux para preparar o ambiente.
#
#  Uso:
#    chmod +x setup-servidor.sh
#    sudo bash setup-servidor.sh
# =================================================================

set -e

REPO_URL="https://github.com/roccorenan/CISP.git"
APP_DIR="/opt/cisp"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║      Setup Servidor — Portal CISP                ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── 1. Atualiza pacotes do sistema ───────────────────────────
echo "📦 Atualizando pacotes do sistema..."
apt-get update -qq && apt-get upgrade -y -qq

# ── 2. Instala Git ────────────────────────────────────────────
echo "📥 Instalando Git..."
apt-get install -y -qq git curl

# ── 3. Instala Docker ─────────────────────────────────────────
if command -v docker &> /dev/null; then
    echo "✅ Docker já instalado: $(docker --version)"
else
    echo "🐳 Instalando Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    echo "✅ Docker instalado"
fi

# ── 4. Instala Docker Compose ─────────────────────────────────
if command -v docker-compose &> /dev/null; then
    echo "✅ Docker Compose já instalado: $(docker-compose --version)"
else
    echo "🐳 Instalando Docker Compose..."
    COMPOSE_VER=$(curl -s https://api.github.com/repos/docker/compose/releases/latest \
        | grep '"tag_name"' | cut -d'"' -f4)
    curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VER}/docker-compose-linux-x86_64" \
        -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "✅ Docker Compose ${COMPOSE_VER} instalado"
fi

# ── 5. Cria diretório e clona o repositório ───────────────────
echo ""
echo "📁 Preparando diretório ${APP_DIR}..."
mkdir -p "$APP_DIR"

if [ -d "${APP_DIR}/.git" ]; then
    echo "✅ Repositório já existe, fazendo git pull..."
    cd "$APP_DIR" && git pull origin main
else
    echo "📥 Clonando https://github.com/roccorenan/CISP ..."
    git clone "$REPO_URL" "$APP_DIR"
    echo "✅ Repositório clonado"
fi

cd "$APP_DIR"

# ── 6. Cria o arquivo .env com as credenciais ─────────────────
echo ""
if [ -f "${APP_DIR}/.env" ]; then
    echo "✅ Arquivo .env já existe, pulando criação"
    echo "   Para editar: nano ${APP_DIR}/.env"
else
    echo "🔐 Configurando variáveis de ambiente..."
    echo "   (ficam SOMENTE no servidor, nunca no Git)"
    echo ""

    read -rp  "  CISP_USERNAME [WS15401]: "            CISP_USERNAME
    CISP_USERNAME=${CISP_USERNAME:-WS15401}

    read -rsp "  CISP_PASSWORD: "                      CISP_PASSWORD; echo

    read -rsp "  POSTGRES (senha do banco): "          POSTGRES; echo

    read -rp  "  DB_HOST [127.0.0.1]: "                DB_HOST
    DB_HOST=${DB_HOST:-127.0.0.1}

    read -rp  "  DB_PORT [5432]: "                     DB_PORT
    DB_PORT=${DB_PORT:-5432}

    read -rp  "  DB_NAME [dbDataLakePrd]: "            DB_NAME
    DB_NAME=${DB_NAME:-dbDataLakePrd}

    read -rp  "  DB_USER [postgres]: "                 DB_USER
    DB_USER=${DB_USER:-postgres}

    read -rp  "  DB_SCHEMA [scsilverlayer]: "          DB_SCHEMA
    DB_SCHEMA=${DB_SCHEMA:-scsilverlayer}

    cat > "${APP_DIR}/.env" <<EOF
CISP_USERNAME=${CISP_USERNAME}
CISP_PASSWORD=${CISP_PASSWORD}
POSTGRES=${POSTGRES}
DB_HOST=${DB_HOST}
DB_PORT=${DB_PORT}
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_SCHEMA=${DB_SCHEMA}
EOF

    chmod 600 "${APP_DIR}/.env"
    echo ""
    echo "✅ .env criado com permissão 600 (somente root lê)"
fi

# ── 7. Gera chave SSH para o GitHub Actions ───────────────────
echo ""
echo "🔑 Gerando chave SSH para o GitHub Actions..."
SSH_KEY="${HOME}/.ssh/github_actions_cisp"

mkdir -p "${HOME}/.ssh"
chmod 700 "${HOME}/.ssh"

if [ -f "$SSH_KEY" ]; then
    echo "✅ Chave SSH já existe: $SSH_KEY"
else
    ssh-keygen -t ed25519 -C "github-actions@cisp" -f "$SSH_KEY" -N ""

    # Autoriza a chave no próprio servidor
    cat "${SSH_KEY}.pub" >> "${HOME}/.ssh/authorized_keys"
    chmod 600 "${HOME}/.ssh/authorized_keys"

    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  CHAVE PRIVADA — cole no GitHub como secret SERVER_SSH_KEY ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    cat "$SSH_KEY"
    echo ""
    echo "(guarde essa chave — ela não será exibida novamente)"
fi

# ── 8. Primeiro build e start da aplicação ────────────────────
echo ""
echo "🔨 Fazendo o primeiro build da imagem Docker..."
cd "$APP_DIR"
docker-compose build --no-cache

echo "🚀 Subindo a aplicação..."
docker-compose up -d

# ── 9. Aguarda e verifica ─────────────────────────────────────
echo "⏳ Aguardando inicialização (15s)..."
sleep 15
docker-compose ps

# ── 10. Resumo ────────────────────────────────────────────────
SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                  Setup Concluído! ✅                     ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "🌐 Aplicação: http://${SERVER_IP}:5000"
echo "🏥 Health:    http://${SERVER_IP}:5000/api/health"
echo ""
echo "📋 Próximos passos — configure os secrets no GitHub:"
echo ""
echo "   Acesse: https://github.com/roccorenan/CISP/settings/secrets/actions"
echo ""
echo "   SERVER_HOST    = ${SERVER_IP}"
echo "   SERVER_USER    = $(whoami)"
echo "   SERVER_PORT    = 22"
echo "   SERVER_SSH_KEY = (a chave privada exibida acima)"
echo ""
echo "   Depois é só fazer um push na branch main para testar o deploy automático."
echo ""
