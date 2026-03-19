#!/usr/bin/env bash
set -euo pipefail

# Installs/updates systemd units from templates in deploy/systemd/.
# Safe default: make a DB backup before service restart.
#
# Optional overrides:
#   PROJECT_DIR=/home/pi/dognosis
#   PYTHON_BIN=/usr/bin/python3
#   SERVICE_USER=pi
#   DB_PATH=/home/pi/dognosis/dog_harness.db
#   BACKUP_DIR=/home/pi/dognosis/deploy/backups

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
SERVICE_USER="${SERVICE_USER:-$(id -un)}"
SYSTEMD_DIR="/etc/systemd/system"

LOGGER_TEMPLATE="${PROJECT_DIR}/deploy/systemd/dognosis-logger.service"
APP_TEMPLATE="${PROJECT_DIR}/deploy/systemd/dognosis-app.service"
LOGGER_TARGET="${SYSTEMD_DIR}/dognosis-logger.service"
APP_TARGET="${SYSTEMD_DIR}/dognosis-app.service"

if [[ ! -f "${LOGGER_TEMPLATE}" || ! -f "${APP_TEMPLATE}" ]]; then
  echo "Missing service templates in ${PROJECT_DIR}/deploy/systemd"
  exit 1
fi

if [[ ! -x "${PROJECT_DIR}/deploy/backup_db.sh" ]]; then
  chmod +x "${PROJECT_DIR}/deploy/backup_db.sh"
fi

echo "Backing up database before service changes..."
DB_PATH="${DB_PATH:-${PROJECT_DIR}/dog_harness.db}" \
BACKUP_DIR="${BACKUP_DIR:-${PROJECT_DIR}/deploy/backups}" \
"${PROJECT_DIR}/deploy/backup_db.sh"

tmp_logger="$(mktemp)"
tmp_app="$(mktemp)"
trap 'rm -f "${tmp_logger}" "${tmp_app}"' EXIT

sed \
  -e "s|{{PROJECT_DIR}}|${PROJECT_DIR}|g" \
  -e "s|{{PYTHON_BIN}}|${PYTHON_BIN}|g" \
  -e "s|User=pi|User=${SERVICE_USER}|g" \
  "${LOGGER_TEMPLATE}" > "${tmp_logger}"

sed \
  -e "s|{{PROJECT_DIR}}|${PROJECT_DIR}|g" \
  -e "s|{{PYTHON_BIN}}|${PYTHON_BIN}|g" \
  -e "s|User=pi|User=${SERVICE_USER}|g" \
  "${APP_TEMPLATE}" > "${tmp_app}"

echo "Installing systemd units..."
sudo cp "${tmp_logger}" "${LOGGER_TARGET}"
sudo cp "${tmp_app}" "${APP_TARGET}"

echo "Reloading and enabling services..."
sudo systemctl daemon-reload
sudo systemctl enable dognosis-logger.service dognosis-app.service

echo "Restarting services..."
sudo systemctl restart dognosis-logger.service dognosis-app.service

echo
echo "Service status:"
sudo systemctl --no-pager --full status dognosis-logger.service dognosis-app.service || true

echo
echo "To follow logs:"
echo "  journalctl -u dognosis-logger.service -f"
echo "  journalctl -u dognosis-app.service -f"
