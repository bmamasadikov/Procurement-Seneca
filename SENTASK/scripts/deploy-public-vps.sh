#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SSH_TARGET="${SSH_TARGET:-}"
REMOTE_DIR="${REMOTE_DIR:-/opt/sentask}"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.public}"

if [[ -z "$SSH_TARGET" ]]; then
  echo "Missing SSH_TARGET. Example: SSH_TARGET=ubuntu@203.0.113.10"
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE"
  echo "Create it from .env.public.example first."
  exit 1
fi

echo "Deploying SENTASK to $SSH_TARGET:$REMOTE_DIR"

ssh "$SSH_TARGET" "mkdir -p '$REMOTE_DIR'"

rsync -az --delete \
  --exclude ".git" \
  --exclude "node_modules" \
  --exclude ".next" \
  --exclude ".tmp-seed" \
  --exclude ".env" \
  --exclude ".env.public" \
  "$ROOT_DIR/" "$SSH_TARGET:$REMOTE_DIR/"

scp "$ENV_FILE" "$SSH_TARGET:$REMOTE_DIR/.env.public"

ssh "$SSH_TARGET" "
  set -euo pipefail
  cd '$REMOTE_DIR'
  docker compose -f docker-compose.public.yml --env-file .env.public up -d --build
  docker compose -f docker-compose.public.yml --env-file .env.public ps
"

echo "Deployment complete."
