# Dognosis Pi Boot Services

This folder lets you keep boot automation in-repo, then install it on the Pi after pulling.

## Files

- `deploy/systemd/dognosis-logger.service` - template for sensor logger at boot
- `deploy/systemd/dognosis-app.service` - template for Flask app at boot
- `deploy/backup_db.sh` - timestamped SQLite backup helper
- `deploy/install_services.sh` - backup + install/update + enable + restart services

## One-time setup on Pi

1. Pull latest repo on Pi.
2. Make scripts executable:
   - `chmod +x deploy/backup_db.sh deploy/install_services.sh`
3. Install services:
   - `./deploy/install_services.sh`

The install script will:

1. Back up the DB before changes
2. Render service templates with your project path and python path
3. Install units in `/etc/systemd/system`
4. `daemon-reload`, `enable`, and `restart` both services

## Optional overrides

If your environment differs from defaults:

```bash
PROJECT_DIR=/home/pi/dognosis \
PYTHON_BIN=/home/pi/.venv/bin/python \
SERVICE_USER=pi \
DB_PATH=/home/pi/dognosis/dog_harness.db \
BACKUP_DIR=/home/pi/dognosis/deploy/backups \
./deploy/install_services.sh
```

## Manual DB backup

Default:

```bash
./deploy/backup_db.sh
```

With custom paths:

```bash
DB_PATH=/home/pi/dognosis/dog_harness.db \
BACKUP_DIR=/home/pi/dognosis/backups \
./deploy/backup_db.sh
```

## Useful checks

- `systemctl status dognosis-logger.service`
- `systemctl status dognosis-app.service`
- `journalctl -u dognosis-logger.service -f`
- `journalctl -u dognosis-app.service -f`
