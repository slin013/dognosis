#!/usr/bin/env bash
set -euo pipefail

# Backs up the on-device SQLite database to deploy/backups by default.
# Override defaults with:
#   DB_PATH=/path/to/dog_harness.db BACKUP_DIR=/path/to/backups ./deploy/backup_db.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

DB_PATH="${DB_PATH:-${PROJECT_DIR}/dog_harness.db}"
BACKUP_DIR="${BACKUP_DIR:-${SCRIPT_DIR}/backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_PATH="${BACKUP_DIR}/dog_harness_${TIMESTAMP}.db"

mkdir -p "${BACKUP_DIR}"

if [[ ! -f "${DB_PATH}" ]]; then
  echo "Database not found at: ${DB_PATH}"
  exit 1
fi

echo "Creating backup:"
echo "  Source: ${DB_PATH}"
echo "  Dest:   ${BACKUP_PATH}"

# Use sqlite online backup when available; fall back to cp.
if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "${DB_PATH}" ".backup '${BACKUP_PATH}'"
else
  cp "${DB_PATH}" "${BACKUP_PATH}"
fi

echo "Backup complete."
