#!/bin/bash
# =============================================================================
# deploy-ubuntu.sh — Setup inicial da VM Ubuntu Server 24.04
# Execute como root ou com sudo: sudo bash deploy-ubuntu.sh
# =============================================================================
set -e

APP_DIR="/opt/cisp"
COMPOSE_FILE="$APP_DIR/docker-compose.yml"

echo "==> Atualizando pacotes..."
apt-get update -qq

echo "==> Instalando Docker..."
apt-get install -y ca-certificates curl gnupg lsb-release
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -qq
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

echo "==> Habilitando Docker no boot..."
systemctl enable docker
systemctl start docker

echo "==> Copiando projeto para $APP_DIR..."
mkdir -p "$APP_DIR"
cp -r . "$APP_DIR"
cd "$APP_DIR"

# Verifica se .env existe, se não, cria a partir do exemplo
if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env.docker.example" "$APP_DIR/.env"
  echo ""
  echo "============================================================"
  echo "  ATENÇÃO: Arquivo .env criado a partir do exemplo."
  echo "  Edite $APP_DIR/.env antes de continuar:"
  echo "    nano $APP_DIR/.env"
  echo "============================================================"
  echo ""
  echo "  Após editar, execute:"
  echo "    cd $APP_DIR && docker compose up -d --build"
  echo ""
  exit 0
fi

echo "==> Construindo e subindo containers..."
docker compose up -d --build

echo ""
echo "==> Verificando saúde da aplicação..."
sleep 3
curl -sf http://localhost:5000/api/health && echo " OK" || echo " Aguarde alguns segundos e tente: curl http://localhost:5000/api/health"

echo ""
echo "============================================================"
echo "  Deploy concluído!"
echo "  Acesse: http://$(hostname -I | awk '{print $1}'):5000"
echo "============================================================"
