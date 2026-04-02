#!/bin/bash

set -uo pipefail

SCRIPT_NAME="$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SSOT_DIR="$REPO_DIR/ssot"
MODEL="minimax/MiniMax-M2.5"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
RESET='\033[0m'

processed=0
failed=0
skipped=0
total_orig_tokens=0
total_new_tokens=0

usage() {
    cat <<EOF
Usage:
  ./$SCRIPT_NAME path/to/SSOT-L1-SHIELD.md
  ./$SCRIPT_NAME --all
EOF
}

estimate_tokens() {
    local file_path="$1"
    local chars
    chars=$(wc -c < "$file_path" | tr -d '[:space:]')
    echo $(( (chars + 3) / 4 ))
}

resolve_path() {
    local input_path="$1"

    if [[ "$input_path" = /* ]]; then
        printf '%s\n' "$input_path"
    elif [[ "$input_path" == ssot/* ]]; then
        printf '%s\n' "$REPO_DIR/$input_path"
    else
        printf '%s\n' "$SSOT_DIR/$input_path"
    fi
}

compress_to_file() {
    local src="$1"
    local dest="$2"
    local tmp_output
    local tmp_error

    tmp_output=$(mktemp)
    tmp_error=$(mktemp)

    if ! {
        cat <<EOF
Compress this SSoT document to 30-50% of its original size. Output ONLY the compressed document, nothing else.

Rules:
- First line MUST be: Updated: YYYY-MM-DD
- Second line: [AI-OPTIMIZED] ~XXX tokens | src: FILENAME | Updated: YYYY-MM-DD
- Keep ALL technical facts: names, numbers, paths, versions, dates, config values
- Keep table structure where useful (compress rows, not structure)
- Remove prose, explanations, examples, rationale
- Use terse notation (arrows, pipes, abbreviations)
- Never add information not in the original
- Never omit critical paths, port numbers, or version numbers

Document to compress:

EOF
        cat "$src"
    } | ollama run "$MODEL" >"$tmp_output" 2>"$tmp_error"; then
        printf '%bFAIL%b %s\n' "$RED" "$RESET" "$(basename "$src")"
        sed -n '1,5p' "$tmp_error" >&2
        rm -f "$tmp_output" "$tmp_error"
        return 1
    fi

    if [[ ! -s "$tmp_output" ]]; then
        printf '%bFAIL%b %s\n' "$RED" "$RESET" "$(basename "$src")"
        echo "Empty response from ollama." >&2
        rm -f "$tmp_output" "$tmp_error"
        return 1
    fi

    mv "$tmp_output" "$dest"
    rm -f "$tmp_error"
    return 0
}

process_file() {
    local src="$1"
    local dest
    local orig_tokens
    local new_tokens
    local saved_tokens
    local saved_pct=0

    if [[ ! -f "$src" ]]; then
        printf '%bFAIL%b Missing source: %s\n' "$RED" "$RESET" "$src"
        failed=$((failed + 1))
        return
    fi

    if [[ "$src" != *.md || "$src" == *.ai.md ]]; then
        printf '%bFAIL%b Expected a .md source file: %s\n' "$RED" "$RESET" "$src"
        failed=$((failed + 1))
        return
    fi

    dest="${src%.md}.ai.md"

    printf '%bPROCESSING%b %s\n' "$YELLOW" "$RESET" "$src"

    if ! compress_to_file "$src" "$dest"; then
        failed=$((failed + 1))
        rm -f "$dest"
        return
    fi

    touch -r "$src" "$dest"

    orig_tokens=$(estimate_tokens "$src")
    new_tokens=$(estimate_tokens "$dest")
    saved_tokens=$((orig_tokens - new_tokens))
    if (( orig_tokens > 0 )); then
        saved_pct=$(( saved_tokens * 100 / orig_tokens ))
    fi

    processed=$((processed + 1))
    total_orig_tokens=$((total_orig_tokens + orig_tokens))
    total_new_tokens=$((total_new_tokens + new_tokens))

    printf '%bOK%b %s -> %s | ~%s -> ~%s tokens | saved ~%s (%s%%)\n' \
        "$GREEN" "$RESET" "$(basename "$src")" "$(basename "$dest")" \
        "$orig_tokens" "$new_tokens" "$saved_tokens" "$saved_pct"
}

collect_all_targets() {
    local ai_file
    local src

    while IFS= read -r ai_file; do
        src="${ai_file%.ai.md}.md"
        if [[ -f "$src" ]]; then
            targets+=("$src")
        else
            skipped=$((skipped + 1))
            printf '%bSKIP%b Missing source for %s\n' "$YELLOW" "$RESET" "$ai_file"
        fi
    done < <(find "$SSOT_DIR" -type f -name '*.ai.md' ! -path '*/archive/*' | sort)
}

print_summary() {
    local total_saved
    local total_saved_pct=0

    total_saved=$((total_orig_tokens - total_new_tokens))
    if (( total_orig_tokens > 0 )); then
        total_saved_pct=$(( total_saved * 100 / total_orig_tokens ))
    fi

    echo
    if (( failed == 0 )); then
        printf '%bSummary%b processed=%s skipped=%s failed=%s | ~%s -> ~%s tokens | saved ~%s (%s%%)\n' \
            "$GREEN" "$RESET" "$processed" "$skipped" "$failed" \
            "$total_orig_tokens" "$total_new_tokens" "$total_saved" "$total_saved_pct"
    else
        printf '%bSummary%b processed=%s skipped=%s failed=%s | ~%s -> ~%s tokens | saved ~%s (%s%%)\n' \
            "$RED" "$RESET" "$processed" "$skipped" "$failed" \
            "$total_orig_tokens" "$total_new_tokens" "$total_saved" "$total_saved_pct"
    fi
}

if (( $# == 0 )); then
    usage
    exit 1
fi

if ! command -v ollama >/dev/null 2>&1; then
    printf '%bFAIL%b ollama not found in PATH\n' "$RED" "$RESET" >&2
    exit 1
fi

declare -a targets=()

if (( $# == 1 )) && [[ "$1" == "--all" ]]; then
    collect_all_targets
else
    if (( $# != 1 )); then
        usage
        exit 1
    fi
    targets+=("$(resolve_path "$1")")
fi

if (( ${#targets[@]} == 0 )); then
    print_summary
    exit 0
fi

for src in "${targets[@]}"; do
    process_file "$src"
done

print_summary

if (( failed > 0 )); then
    exit 1
fi

exit 0
