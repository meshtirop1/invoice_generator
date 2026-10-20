#!/usr/bin/env bash
#
# Update the live site. The Deploy workflow (.github/workflows/deploy.yml) SSHes in as the
# deploy user, resets /home/deploy/sites/invoice to origin/main and then runs this script, so
# it is always the newest version of this file that runs. By hand: same two steps.
#
# Untracked files on the server are left alone by the reset: env (settings + secrets),
# db.sqlite3, backups/, staticfiles/ and .venv/.

set -euo pipefail

APP_DIR="/home/deploy/sites/invoice"
ENV_FILE="$APP_DIR/env"
SERVICE="invoice"

log() { printf '\n==> %s\n' "$*"; }

cd "$APP_DIR"

log "Installing/updating dependencies"
.venv/bin/pip install -r requirements.txt --quiet

log "Loading env (systemd EnvironmentFile style; parsed, not sourced)"
. "$APP_DIR/deploy/load_env.sh"

log "Backing up the database before migrating"
# A failed backup stops the deploy: never migrate without a copy to go back to.
.venv/bin/python manage.py backup_db --label predeploy

log "Running Django steps"
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py check

log "Restarting gunicorn"
sudo /usr/bin/systemctl restart "$SERVICE"
sudo /usr/bin/systemctl is-active "$SERVICE"

log "Deploy complete: $(git rev-parse --short HEAD)"
