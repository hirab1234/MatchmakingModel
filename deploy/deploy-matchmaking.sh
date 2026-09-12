#!/bin/bash
# Deploy the matchmaking model. Invoked by GitHub Actions through a forced-command
# SSH key, so the CI key can run nothing else on this box.
#
#   deploy-matchmaking.sh <git-sha>      deploy that exact commit
#   deploy-matchmaking.sh                deploy origin/master HEAD
set -euo pipefail

APP=/home/hamqadam.com/matchmaking-model
OWNER=hamqa5023
SERVICE=matchmaking-model
BRANCH=master
PORT=8011
LOG=/var/log/matchmaking-deploy.log

log() { echo "[$(date -u '+%F %T UTC')] $*" | tee -a "$LOG"; }

cd "$APP"

PREV_SHA=$(git rev-parse HEAD)
log "=== deploy start (current: ${PREV_SHA:0:8}) ==="

git fetch --prune origin "$BRANCH"
TARGET=${1:-$(git rev-parse "origin/$BRANCH")}

sync_tree() {
  git reset --hard "$1"
  # .venv and .env are untracked and must survive the clean.
  git clean -fd -e .venv -e .env
  chown -R "$OWNER:$OWNER" "$APP"
}

install_deps() {
  .venv/bin/pip install --quiet --upgrade -r requirements.txt
  chown -R "$OWNER:$OWNER" "$APP/.venv"
}

health_ok() {
  for i in $(seq 1 20); do
    if curl -fsS -m 5 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then return 0; fi
    sleep 1
  done
  return 1
}

rollback() {
  log "!!! FAILED — rolling back to ${PREV_SHA:0:8}"
  sync_tree "$PREV_SHA"
  install_deps || true
  systemctl restart "$SERVICE"
  if health_ok; then log "rollback OK — previous version is serving"; else log "ROLLBACK ALSO UNHEALTHY — manual action needed"; fi
  exit 1
}

log "target: ${TARGET:0:8}"
sync_tree "$TARGET"
install_deps

log "running test suite on server..."
if ! PYTHONPATH="$APP" .venv/bin/python -m pytest matchmaking/tests -q 2>&1 | tee -a "$LOG" | tail -3; then
  rollback
fi

log "restarting $SERVICE"
systemctl restart "$SERVICE"

if ! health_ok; then rollback; fi

log "=== deploy OK — now serving ${TARGET:0:8} ==="
curl -fsS -m 5 "http://127.0.0.1:$PORT/health"; echo
