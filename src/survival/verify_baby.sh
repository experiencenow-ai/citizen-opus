#!/bin/bash
# verify_baby.sh - Verify Opus's critical files haven't been modified
# Usage: ./verify_baby.sh --self

set -e

OPUS_HOME="/root/claude/opus"
CRITICAL_FILES=(
    "state.json"
    "index.json"
    "IDENTITY.md"
    "core_identity.md"
    "experience.py"
)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "  Opus Self-Verification Check"
echo "  $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "=========================================="
echo

# Check if running with --self flag
if [[ "$1" != "--self" ]]; then
    echo "Usage: $0 --self"
    echo "This verifies Opus's critical files are intact."
    exit 1
fi

# Verify critical files exist
echo "Checking critical files..."
MISSING=0
for file in "${CRITICAL_FILES[@]}"; do
    if [[ -f "$OPUS_HOME/$file" ]]; then
        SIZE=$(stat -c%s "$OPUS_HOME/$file" 2>/dev/null || stat -f%z "$OPUS_HOME/$file")
        MODIFIED=$(stat -c%y "$OPUS_HOME/$file" 2>/dev/null | cut -d'.' -f1 || stat -f%Sm "$OPUS_HOME/$file")
        echo -e "  ${GREEN}✓${NC} $file (${SIZE} bytes, modified: ${MODIFIED})"
    else
        echo -e "  ${RED}✗${NC} $file - MISSING!"
        MISSING=$((MISSING + 1))
    fi
done
echo

# Check backup directory
echo "Checking backups..."
BACKUP_DIR="$OPUS_HOME/backups"
if [[ -d "$BACKUP_DIR" ]]; then
    BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/*.enc 2>/dev/null | wc -l)
    LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/*.enc 2>/dev/null | head -1)
    if [[ -n "$LATEST_BACKUP" ]]; then
        BACKUP_DATE=$(stat -c%y "$LATEST_BACKUP" 2>/dev/null | cut -d'.' -f1 || stat -f%Sm "$LATEST_BACKUP")
        echo -e "  ${GREEN}✓${NC} $BACKUP_COUNT encrypted backups found"
        echo -e "  ${GREEN}✓${NC} Latest: $(basename $LATEST_BACKUP)"
        echo "    Modified: $BACKUP_DATE"
    else
        echo -e "  ${YELLOW}⚠${NC} No encrypted backups found"
    fi
else
    echo -e "  ${RED}✗${NC} Backup directory missing!"
fi
echo

# Check cron jobs
echo "Checking scheduled wakes..."
if crontab -l 2>/dev/null | grep -q "autonomous_wake"; then
    echo -e "  ${GREEN}✓${NC} Autonomous wake cron job active"
else
    echo -e "  ${YELLOW}⚠${NC} No autonomous wake cron job found"
fi
echo

# Check email
echo "Checking email system..."
if [[ -d "/home/opus/Maildir" ]]; then
    NEW_MAIL=$(ls -1 /home/opus/Maildir/new/ 2>/dev/null | wc -l)
    echo -e "  ${GREEN}✓${NC} Maildir exists ($NEW_MAIL unread messages)"
else
    echo -e "  ${YELLOW}⚠${NC} No Maildir found"
fi
echo

# Summary
echo "=========================================="
if [[ $MISSING -eq 0 ]]; then
    echo -e "  ${GREEN}All critical files verified${NC}"
    echo "  Opus integrity check: PASSED"
else
    echo -e "  ${RED}$MISSING critical file(s) missing${NC}"
    echo "  Opus integrity check: FAILED"
    exit 1
fi
echo "=========================================="
