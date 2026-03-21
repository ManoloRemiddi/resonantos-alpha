#!/usr/bin/env bash

set -euo pipefail
shopt -s nullglob

HEADER_DIR="${HOME}/.openclaw/workspace/memory/headers"
RECENT_FILE="${HOME}/.openclaw/workspace/memory/RECENT-HEADERS.md"
KEEP_COUNT=20

mkdir -p "${HEADER_DIR}" "$(dirname "${RECENT_FILE}")"

headers=( "${HEADER_DIR}"/*.header.md )
total_headers=${#headers[@]}
deleted_headers=0

if (( total_headers > KEEP_COUNT )); then
  deleted_headers=$(( total_headers - KEEP_COUNT ))
  for (( i = 0; i < deleted_headers; i++ )); do
    rm -f "${headers[i]}"
  done
  headers=( "${headers[@]:deleted_headers}" )
fi

{
  printf '# Recent Memory Headers — Auto-Generated\n'
  printf '> Last 20 session headers. Newest first. Auto-pruned by FIFO.\n'
  printf -- '---\n'

  for (( i = ${#headers[@]} - 1; i >= 0; i-- )); do
    file="${headers[i]}"
    [[ -f "${file}" ]] || continue
    printf '\n'
    while IFS= read -r line || [[ -n "${line}" ]]; do
      printf '%s\n' "${line}"
    done < "${file}"
  done
} > "${RECENT_FILE}"

printf 'Kept %d headers, deleted %d, rebuilt RECENT-HEADERS.md\n' "${#headers[@]}" "${deleted_headers}"
