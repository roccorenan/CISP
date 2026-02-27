#!/usr/bin/env bash
set -e
REPO_URL="$1"
BRANCH="${2:-main}"
APP_DIR="${3:-/opt/cisp}"
INTERVAL="${4:-5min}"
COMPOSE_FILE="${5:-docker-compose.linux.nginx.yml}"
UNIT_DIR="/etc/systemd/system"
SERVICE_NAME="cisp-update.service"
TIMER_NAME="cisp-update.timer"
if [ -z "$REPO_URL" ]; then echo "repo"; exit 1; fi
cat > "$UNIT_DIR/$SERVICE_NAME" <<EOF
[Unit]
Description=CISP update and restart
After=network.target docker.service
[Service]
Type=oneshot
Environment=REPO_URL=$REPO_URL
Environment=BRANCH=$BRANCH
Environment=APP_DIR=$APP_DIR
Environment=COMPOSE_FILE=$COMPOSE_FILE
ExecStart=/usr/bin/env bash $APP_DIR/scripts/linux/deploy.sh
EOF
cat > "$UNIT_DIR/$TIMER_NAME" <<EOF
[Unit]
Description=CISP periodic updater
[Timer]
OnUnitActiveSec=$INTERVAL
OnBootSec=2min
Unit=$SERVICE_NAME
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now "$TIMER_NAME"
