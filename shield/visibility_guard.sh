#!/bin/bash
# ============================================================================
# Visibility Guard — Deterministic blocker for repo visibility changes
# ============================================================================
# Wraps `gh` to prevent making repos public except allowlisted ones.
# Install: source this or add to PATH before /opt/homebrew/bin.
#
# ALLOWLIST: Only these repos can be made public without unlock:
#   - ResonantOS public repositories explicitly configured below
#
# UNLOCK: Use shield_lock.py to temporarily allow non-alpha public changes.
#   python3 shield/shield_lock.py unlock <macos-password> [ttl]
#
# This script is called by the gh-wrapper. Do not call directly.
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHIELD_DIR="$SCRIPT_DIR"
SHIELD_LOCK="$SHIELD_DIR/shield_lock.py"
LOG_DIR="$SHIELD_DIR/alerts"
LOG_FILE="$LOG_DIR/visibility_guard.log"
REAL_GH="/opt/homebrew/bin/gh"

# --- Allowlist (exact match, case-sensitive) ---
ALLOWED_PUBLIC_REPOS=(
    "resonantos/resonantos-alpha"
)

mkdir -p "$LOG_DIR"

log_event() {
    local level="$1" msg="$2"
    echo "$(date -u +%FT%TZ) [$level] $msg" >> "$LOG_FILE"
}

is_allowed_repo() {
    local repo="$1"
    for allowed in "${ALLOWED_PUBLIC_REPOS[@]}"; do
        if [[ "$repo" == "$allowed" ]]; then
            return 0
        fi
    done
    return 1
}

is_shield_unlocked() {
    python3 "$SHIELD_LOCK" verify 2>/dev/null
    # exit 0 = locked (gate active), exit 1 = unlocked (gate inactive)
    if [[ $? -eq 1 ]]; then
        return 0  # unlocked
    fi
    return 1  # locked
}

# --- Detect visibility-public in `gh repo edit` ---
check_repo_edit() {
    local args=("$@")
    local has_visibility_public=false
    local target_repo=""
    local i=0

    # Parse: gh repo edit [REPO] --visibility public
    while [[ $i -lt ${#args[@]} ]]; do
        local arg="${args[$i]}"
        case "$arg" in
            --visibility)
                if [[ $((i+1)) -lt ${#args[@]} ]]; then
                    local vis="${args[$((i+1))]}"
                    if [[ "$vis" == "public" ]]; then
                        has_visibility_public=true
                    fi
                    ((i+=2))
                else
                    ((i++))
                fi
                ;;
            --visibility=*)
                local vis="${arg#--visibility=}"
                if [[ "$vis" == "public" ]]; then
                    has_visibility_public=true
                fi
                ((i++))
                ;;
            --*)
                # skip other flags (some take values, some don't)
                ((i++))
                ;;
            *)
                # positional = repo name (first non-flag after "repo edit")
                if [[ -z "$target_repo" ]]; then
                    target_repo="$arg"
                fi
                ((i++))
                ;;
        esac
    done

    if [[ "$has_visibility_public" == "true" ]]; then
        # If no explicit repo, try to infer from cwd
        if [[ -z "$target_repo" ]]; then
            target_repo=$("$REAL_GH" repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "UNKNOWN")
        fi

        if is_allowed_repo "$target_repo"; then
            log_event "ALLOW" "visibility->public for ALLOWLISTED repo: $target_repo"
            return 0  # allowed
        fi

        # Not in allowlist — check unlock
        if is_shield_unlocked; then
            log_event "ALLOW_UNLOCK" "visibility->public for $target_repo (shield unlocked)"
            return 0
        fi

        # BLOCKED
        log_event "BLOCK" "visibility->public BLOCKED for repo: $target_repo"
        echo ""
        echo "╔══════════════════════════════════════════════════════════════╗"
        echo "║  🛡️  VISIBILITY GUARD — BLOCKED                             ║"
        echo "╠══════════════════════════════════════════════════════════════╣"
        echo "║  Cannot make '$target_repo' public."
        echo "║  Only explicitly allowlisted public repositories are allowed."
        echo "║                                                              ║"
        echo "║  To temporarily unlock (human-only):                         ║"
        echo "║    python3 shield_lock.py unlock <macos-password> [ttl]      ║"
        echo "║  Then re-run this command within the unlock window.          ║"
        echo "╚══════════════════════════════════════════════════════════════╝"
        echo ""
        return 1  # blocked
    fi

    return 0  # not a visibility-public command
}

# --- Detect visibility mutations in `gh api` ---
check_api_visibility() {
    local args_str="$*"

    # Pattern: gh api repos/{owner}/{repo} with PATCH and "private":false or "visibility":"public"
    # Also catches: gh api -X PATCH /repos/... with body containing visibility
    if echo "$args_str" | grep -qiE '(repos/|/repos/)' && \
       echo "$args_str" | grep -qiE '("private"\s*:\s*false|"visibility"\s*:\s*"public"|private.*false|visibility.*public)'; then

        # Extract repo from URL pattern
        local target_repo
        target_repo=$(echo "$args_str" | grep -oE 'repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+' | head -1 | sed 's|repos/||')

        if [[ -n "$target_repo" ]] && is_allowed_repo "$target_repo"; then
            log_event "ALLOW" "API visibility->public for ALLOWLISTED repo: $target_repo"
            return 0
        fi

        if is_shield_unlocked; then
            log_event "ALLOW_UNLOCK" "API visibility->public for ${target_repo:-UNKNOWN} (shield unlocked)"
            return 0
        fi

        log_event "BLOCK" "API visibility->public BLOCKED: $args_str"
        echo ""
        echo "╔══════════════════════════════════════════════════════════════╗"
        echo "║  🛡️  VISIBILITY GUARD — API MUTATION BLOCKED                ║"
        echo "╠══════════════════════════════════════════════════════════════╣"
        echo "║  Detected attempt to make a repo public via gh api.          ║"
        echo "║  This is blocked by default. Unlock shield first.            ║"
        echo "╚══════════════════════════════════════════════════════════════╝"
        echo ""
        return 1
    fi

    return 0
}

# --- Main dispatch (called by gh wrapper) ---
# Usage: visibility_guard.sh check-repo-edit [args...]
#        visibility_guard.sh check-api [args...]
case "${1:-}" in
    check-repo-edit)
        shift
        check_repo_edit "$@"
        ;;
    check-api)
        shift
        check_api_visibility "$@"
        ;;
    test)
        # Self-test mode
        echo "=== Visibility Guard Self-Test ==="
        echo ""
        echo "Test 1: alpha repo -> public (should ALLOW)"
        check_repo_edit "resonantos/resonantos-alpha" "--visibility" "public" && echo "  ✅ ALLOWED" || echo "  ❌ BLOCKED"
        echo ""
        echo "Test 2: augmentor repo -> public (should BLOCK)"
        check_repo_edit "resonantos/resonantos-private" "--visibility" "public" && echo "  ❌ ALLOWED (BAD)" || echo "  ✅ BLOCKED"
        echo ""
        echo "Test 3: random repo -> public (should BLOCK)"
        check_repo_edit "someone/something" "--visibility" "public" && echo "  ❌ ALLOWED (BAD)" || echo "  ✅ BLOCKED"
        echo ""
        echo "Test 4: alpha repo -> private (should ALLOW — not a public change)"
        check_repo_edit "resonantos/resonantos-alpha" "--visibility" "private" && echo "  ✅ ALLOWED" || echo "  ❌ BLOCKED"
        echo ""
        echo "Test 5: API mutation with private:false for non-alpha (should BLOCK)"
        check_api_visibility "-X" "PATCH" "/repos/resonantos/resonantos-private" "-f" '"private":false' && echo "  ❌ ALLOWED (BAD)" || echo "  ✅ BLOCKED"
        echo ""
        echo "Test 6: API mutation for alpha (should ALLOW)"
        check_api_visibility "-X" "PATCH" "/repos/resonantos/resonantos-alpha" "-f" '"visibility":"public"' && echo "  ✅ ALLOWED" || echo "  ❌ BLOCKED"
        echo ""
        echo "=== Shield unlock status ==="
        is_shield_unlocked && echo "  🔓 UNLOCKED" || echo "  🔒 LOCKED"
        ;;
    *)
        echo "Usage: visibility_guard.sh {check-repo-edit|check-api|test} [args...]"
        exit 1
        ;;
esac
