#!/bin/bash
#
# token_rotation_ctl.sh - Token Rotation Control Script
#
# Commands: install, uninstall, status, rotate-now, logs
#
# Part of ResonantOS Security Layer
#

set -euo pipefail

# === Configuration ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROTATION_SCRIPT="${SCRIPT_DIR}/rotate_gateway_token.sh"
PLIST_NAME="com.resonantos.token-rotation"
PLIST_SOURCE="${SCRIPT_DIR}/${PLIST_NAME}.plist"
PLIST_DEST="${HOME}/Library/LaunchAgents/${PLIST_NAME}.plist"
LOG_FILE="${HOME}/Library/Logs/resonantos/token_rotation.log"

# === Colors ===
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# === Utilities ===
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
die()     { error "$*"; exit 1; }

# === Commands ===

cmd_install() {
    info "Installing token rotation service..."
    
    # Check rotation script exists
    [[ -f "$ROTATION_SCRIPT" ]] || die "Rotation script not found: $ROTATION_SCRIPT"
    
    # Check plist exists
    [[ -f "$PLIST_SOURCE" ]] || die "Plist file not found: $PLIST_SOURCE"
    
    # Make rotation script executable
    chmod +x "$ROTATION_SCRIPT"
    
    # Create LaunchAgents directory if needed
    mkdir -p "${HOME}/Library/LaunchAgents"
    
    # Copy plist (with user home expansion)
    sed "s|\${HOME}|${HOME}|g" "$PLIST_SOURCE" > "$PLIST_DEST"
    
    # Load the service
    if launchctl list | grep -q "$PLIST_NAME"; then
        info "Service already loaded, reloading..."
        launchctl unload "$PLIST_DEST" 2>/dev/null || true
    fi
    
    launchctl load "$PLIST_DEST"
    
    success "Token rotation service installed"
    info "Service will run every 4 hours at: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00"
    info "Logs at: $LOG_FILE"
    
    # Show status
    cmd_status
}

cmd_uninstall() {
    info "Uninstalling token rotation service..."
    
    if [[ -f "$PLIST_DEST" ]]; then
        launchctl unload "$PLIST_DEST" 2>/dev/null || true
        rm -f "$PLIST_DEST"
        success "Service uninstalled"
    else
        warn "Service was not installed"
    fi
}

cmd_status() {
    echo ""
    echo -e "${BLUE}=== Token Rotation Service Status ===${NC}"
    echo ""
    
    # Check if plist exists
    if [[ -f "$PLIST_DEST" ]]; then
        success "Plist installed: $PLIST_DEST"
    else
        warn "Plist not installed"
    fi
    
    # Check if service is loaded
    if launchctl list 2>/dev/null | grep -q "$PLIST_NAME"; then
        success "Service loaded in launchd"
        
        # Get last exit status
        local exit_status=$(launchctl list | grep "$PLIST_NAME" | awk '{print $2}')
        if [[ "$exit_status" == "0" ]] || [[ "$exit_status" == "-" ]]; then
            success "Last run: success (exit $exit_status)"
        else
            warn "Last run: exit code $exit_status"
        fi
    else
        warn "Service not loaded"
    fi
    
    # Show last rotation
    if [[ -f "$LOG_FILE" ]]; then
        echo ""
        info "Last 3 log entries:"
        tail -n 3 "$LOG_FILE" | while read -r line; do
            echo "  $line"
        done
    else
        warn "No log file yet"
    fi
    
    # Show schedule
    echo ""
    info "Schedule: Every 4 hours (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)"
    
    # Calculate next run
    local current_hour=$(date +%H)
    local next_hour
    for h in 0 4 8 12 16 20 24; do
        if [[ $h -gt $current_hour ]]; then
            next_hour=$h
            break
        fi
    done
    [[ $next_hour -eq 24 ]] && next_hour=0
    printf "  Next rotation: %02d:00\n" "$next_hour"
    
    echo ""
}

cmd_rotate_now() {
    local force_flag=""
    
    # Check for --force flag
    if [[ "${1:-}" == "--force" ]] || [[ "${1:-}" == "-f" ]]; then
        force_flag="--force"
        info "Triggering manual token rotation (FORCE mode - skip coordination)..."
    else
        info "Triggering manual token rotation (with coordination)..."
    fi
    
    if [[ ! -f "$ROTATION_SCRIPT" ]]; then
        die "Rotation script not found: $ROTATION_SCRIPT"
    fi
    
    if [[ ! -x "$ROTATION_SCRIPT" ]]; then
        chmod +x "$ROTATION_SCRIPT"
    fi
    
    # Run the rotation script
    "$ROTATION_SCRIPT" $force_flag
    
    local exit_code=$?
    if [[ $exit_code -eq 0 ]]; then
        success "Manual rotation completed successfully"
    else
        error "Rotation failed with exit code $exit_code"
        exit $exit_code
    fi
}

cmd_logs() {
    local lines="${1:-50}"
    
    if [[ -f "$LOG_FILE" ]]; then
        info "Last $lines lines from: $LOG_FILE"
        echo ""
        tail -n "$lines" "$LOG_FILE"
    else
        warn "No log file found at: $LOG_FILE"
    fi
}

cmd_help() {
    cat << EOF
Token Rotation Control Script
==============================

Usage: $(basename "$0") <command> [options]

Commands:
  install          Install and enable the launchd service
  uninstall        Disable and remove the launchd service
  status           Show service status and recent logs
  rotate-now       Trigger token rotation (waits for active sessions)
  rotate-now -f    Trigger immediate rotation (skip coordination)
  logs [n]         Show last n log entries (default: 50)
  help             Show this help message

Examples:
  $(basename "$0") install           # Enable automatic 4-hour rotation
  $(basename "$0") rotate-now        # Rotate (waits if agents busy)
  $(basename "$0") rotate-now -f     # Force rotate immediately
  $(basename "$0") status            # Check service health
  $(basename "$0") logs 20           # View last 20 log entries

Coordination-Aware Rotation:
  - Checks gateway for active sessions before rotating
  - Waits up to 5 minutes for agents to finish (30s intervals)
  - Force rotates after 5 min (safety override)
  - Use --force/-f to skip coordination (emergency use)

Security Notes:
  - Tokens are 192-bit cryptographically secure random values
  - Old tokens are immediately invalidated after rotation
  - Config updates are atomic (temp file + move)
  - All rotations are logged with timestamp and token hashes
  - Backups kept for last 30 rotations

EOF
}

# === Main ===
main() {
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        install)     cmd_install ;;
        uninstall)   cmd_uninstall ;;
        status)      cmd_status ;;
        rotate-now)  cmd_rotate_now ;;
        logs)        cmd_logs "$@" ;;
        help|--help|-h) cmd_help ;;
        *)
            error "Unknown command: $command"
            echo ""
            cmd_help
            exit 1
            ;;
    esac
}

main "$@"
