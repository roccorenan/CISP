#!/usr/bin/env bash
set -e
REPO_URL="${REPO_URL:-}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-/opt/cisp}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.linux.yml}"
if [ -z "$REPO_URL" ]; then echo "repo"; exit 1; fi
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch origin "$BRANCH"
  LOCAL="$(git -C "$APP_DIR" rev-parse HEAD || echo "")"
  REMOTE="$(git -C "$APP_DIR" rev-parse "origin/$BRANCH" || echo "")"
  if [ "$LOCAL" = "$REMOTE" ] && [ -n "$LOCAL" ]; then
    exit 0
  fi
  git -C "$APP_DIR" reset --hard "origin/$BRANCH"
else
  mkdir -p "$APP_DIR"
  git clone -b "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"
docker compose -f "$COMPOSE_FILE" build
docker compose -f "$COMPOSE_FILE" up -d
