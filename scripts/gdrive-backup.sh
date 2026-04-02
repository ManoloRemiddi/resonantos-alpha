#!/bin/bash
# Encrypted backup to Google Drive
# Uses gog (Google Workspace CLI) + gpg symmetric encryption

set -e

# Configuration
BACKUP_NAME="resonantos-backup-$(date +%Y%m%d-%H%M%S)"
TEMP_DIR="/tmp/gdrive-backup-$$"
PASSWORD_FILE="$HOME/.guardian/backup_password.txt"
LOG_FILE="$HOME/.clawdbot/logs/gdrive-backup.log"
GDRIVE_FOLDER="ResonantOS-Backups"

# Essential directories to backup (under 1GB total)
BACKUP_DIRS=(
    "$HOME/clawd/agents"                    # Agent workspaces (233M)
    "$HOME/clawd/projects/resonantos"       # Main project (515M)
    "$HOME/clawd/projects/logician"         # Policy engine (94M)
    "$HOME/clawd/memory"                    # Memory databases (6M)
    "$HOME/.clawdbot/agents"                # Session history (114M)
    "$HOME/.guardian"                       # Credentials (48K)
)

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Ensure password exists
if [ ! -f "$PASSWORD_FILE" ]; then
    log "Generating backup encryption password..."
    openssl rand -base64 32 > "$PASSWORD_FILE"
    chmod 600 "$PASSWORD_FILE"
    log "Password saved to $PASSWORD_FILE"
fi

PASSWORD=$(cat "$PASSWORD_FILE")

log "Starting encrypted backup: $BACKUP_NAME"

# Create temp directory
mkdir -p "$TEMP_DIR"
trap "rm -rf $TEMP_DIR" EXIT

# Create tarball (excluding .git objects, node_modules, venv, cache)
log "Creating archive..."
tar -czf "$TEMP_DIR/$BACKUP_NAME.tar.gz" \
    --exclude=".git/objects" \
    --exclude="node_modules" \
    --exclude="venv" \
    --exclude="__pycache__" \
    --exclude="*.pyc" \
    --exclude="*.log" \
    "${BACKUP_DIRS[@]}" 2>/dev/null || true

ARCHIVE_SIZE=$(du -sh "$TEMP_DIR/$BACKUP_NAME.tar.gz" | cut -f1)
log "Archive size: $ARCHIVE_SIZE"

# Encrypt with gpg (symmetric)
log "Encrypting..."
gpg --batch --yes --passphrase "$PASSWORD" --symmetric \
    --cipher-algo AES256 \
    -o "$TEMP_DIR/$BACKUP_NAME.tar.gz.gpg" \
    "$TEMP_DIR/$BACKUP_NAME.tar.gz"

ENCRYPTED_SIZE=$(du -sh "$TEMP_DIR/$BACKUP_NAME.tar.gz.gpg" | cut -f1)
log "Encrypted size: $ENCRYPTED_SIZE"

# Upload to Google Drive
log "Uploading to Google Drive ($GDRIVE_FOLDER)..."
gog drive upload "$TEMP_DIR/$BACKUP_NAME.tar.gz.gpg" \
    --parent "$GDRIVE_FOLDER" \
    --account "${GDRIVE_ACCOUNT}" 2>&1 | tee -a "$LOG_FILE"

log "✅ Backup complete: $BACKUP_NAME.tar.gz.gpg ($ENCRYPTED_SIZE)"

# Cleanup old backups (keep last 7)
log "Cleaning up old backups..."
gog drive ls "$GDRIVE_FOLDER" --account "${GDRIVE_ACCOUNT}" 2>/dev/null | \
    grep "resonantos-backup-" | \
    sort -r | \
    tail -n +8 | \
    while read -r line; do
        FILE_ID=$(echo "$line" | awk '{print $1}')
        if [ -n "$FILE_ID" ]; then
            gog drive rm "$FILE_ID" --account "${GDRIVE_ACCOUNT}" 2>/dev/null || true
            log "Deleted old backup: $FILE_ID"
        fi
    done

log "Done."
