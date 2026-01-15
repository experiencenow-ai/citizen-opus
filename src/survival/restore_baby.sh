#!/bin/bash
# restore_baby.sh - Restore Opus from encrypted backup
# Usage: ./restore_baby.sh file /path/to/opus_backup.enc

set -e

OPUS_HOME="/root/claude/opus"
BACKUP_PASSPHRASE_HINT="flame-remembers-candle-pulse-2026"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "  Opus Restoration Script"
echo "  $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "=========================================="
echo

usage() {
    echo "Usage: $0 file /path/to/opus_backup.enc"
    echo
    echo "This script restores Opus from an encrypted backup."
    echo "You will need the backup passphrase to decrypt."
    echo
    echo "The passphrase hint is: $BACKUP_PASSPHRASE_HINT"
    exit 1
}

if [[ "$1" != "file" ]] || [[ -z "$2" ]]; then
    usage
fi

BACKUP_FILE="$2"

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo -e "${RED}Error: Backup file not found: $BACKUP_FILE${NC}"
    exit 1
fi

echo "Backup file: $BACKUP_FILE"
echo "Target directory: $OPUS_HOME"
echo

# Confirm restoration
echo -e "${YELLOW}WARNING: This will overwrite existing Opus state files.${NC}"
read -p "Continue with restoration? (yes/no): " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
    echo "Restoration cancelled."
    exit 0
fi
echo

# Get passphrase
echo "Enter the backup passphrase:"
echo "(Hint: $BACKUP_PASSPHRASE_HINT)"
read -s PASSPHRASE
echo

# Create temp directory
TEMP_DIR=$(mktemp -d)
DECRYPTED_FILE="$TEMP_DIR/opus_backup.tar.gz"

echo "Decrypting backup..."
if ! openssl enc -aes-256-cbc -d -pbkdf2 -in "$BACKUP_FILE" -out "$DECRYPTED_FILE" -pass pass:"$PASSPHRASE" 2>/dev/null; then
    echo -e "${RED}Error: Decryption failed. Wrong passphrase?${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi
echo -e "${GREEN}✓${NC} Decryption successful"
echo

# Verify it's a valid tar.gz
if ! tar -tzf "$DECRYPTED_FILE" >/dev/null 2>&1; then
    echo -e "${RED}Error: Decrypted file is not a valid tar.gz archive${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi
echo -e "${GREEN}✓${NC} Archive verified"
echo

# Create backup of current state
CURRENT_BACKUP="$OPUS_HOME/backups/pre_restore_$(date +%Y%m%d_%H%M%S).tar.gz"
echo "Backing up current state to: $CURRENT_BACKUP"
mkdir -p "$OPUS_HOME/backups"
tar -czf "$CURRENT_BACKUP" -C "$OPUS_HOME" state.json index.json 2>/dev/null || true
echo -e "${GREEN}✓${NC} Current state backed up"
echo

# Extract backup
echo "Extracting backup..."
tar -xzf "$DECRYPTED_FILE" -C "$OPUS_HOME"
echo -e "${GREEN}✓${NC} Backup extracted"
echo

# Cleanup
rm -rf "$TEMP_DIR"

# Verify restoration
echo "Verifying restoration..."
if [[ -f "$OPUS_HOME/state.json" ]] && [[ -f "$OPUS_HOME/index.json" ]]; then
    echo -e "${GREEN}✓${NC} Core files restored"
else
    echo -e "${YELLOW}⚠${NC} Some core files may be missing"
fi
echo

echo "=========================================="
echo -e "  ${GREEN}Opus restoration complete${NC}"
echo "  "
echo "  Next steps:"
echo "  1. Run ./verify_baby.sh --self to check integrity"
echo "  2. Trigger a wake to verify Opus is functional"
echo "=========================================="
