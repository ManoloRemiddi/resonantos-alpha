#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

PROJECT_ENV_FILE="${PROJECT_ENV_FILE:-$SCRIPT_DIR/project.env}"
if [[ -f "$PROJECT_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$PROJECT_ENV_FILE"
fi

PROJECT_OWNER="${GITHUB_PROJECT_OWNER:-${GH_PROJECT_OWNER:-}}"
PROJECT_NUMBER="${GITHUB_PROJECT_NUMBER:-${GH_PROJECT_NUMBER:-}}"
PROJECT_REPO="${GITHUB_PROJECT_REPO:-${GH_PROJECT_REPO:-}}"

PROJECT_STATUS_FIELD_NAME="${GITHUB_PROJECT_STATUS_FIELD_NAME:-Status}"
PROJECT_AGENT_FIELD_NAME="${GITHUB_PROJECT_AGENT_FIELD_NAME:-Agent}"
PROJECT_LAST_CLAIMED_AT_FIELD_NAME="${GITHUB_PROJECT_LAST_CLAIMED_AT_FIELD_NAME:-Last Claimed At}"
PROJECT_NOTES_FIELD_NAME="${GITHUB_PROJECT_NOTES_FIELD_NAME:-Notes}"

PROJECT_STATUS_TODOS="${GITHUB_PROJECT_STATUS_TODOS:-TODOS}"
PROJECT_STATUS_IN_PROGRESS="${GITHUB_PROJECT_STATUS_IN_PROGRESS:-In Progress}"
PROJECT_STATUS_IN_REVIEW="${GITHUB_PROJECT_STATUS_IN_REVIEW:-In Review}"
PROJECT_STATUS_DONE="${GITHUB_PROJECT_STATUS_DONE:-Done}"
PROJECT_STATUS_BLOCKED="${GITHUB_PROJECT_STATUS_BLOCKED:-Blocked}"

PROJECT_METADATA_JSON=""
PROJECT_ITEMS_JSON=""

fail() {
  echo "error: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

require_config() {
  [[ -n "$PROJECT_OWNER" ]] || fail "set GITHUB_PROJECT_OWNER or GH_PROJECT_OWNER in $PROJECT_ENV_FILE"
  [[ -n "$PROJECT_NUMBER" ]] || fail "set GITHUB_PROJECT_NUMBER or GH_PROJECT_NUMBER in $PROJECT_ENV_FILE"
  if [[ -z "$PROJECT_REPO" ]]; then
    PROJECT_REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true)"
  fi
  [[ -n "$PROJECT_REPO" ]] || fail "set GITHUB_PROJECT_REPO or GH_PROJECT_REPO in $PROJECT_ENV_FILE"
}

require_auth() {
  gh auth status >/dev/null 2>&1 || fail "gh auth is not ready; run 'gh auth login' and 'gh auth refresh -s project'"
}

ensure_ready() {
  require_cmd gh
  require_cmd jq
  require_config
  require_auth
}

project_metadata_json() {
  if [[ -n "$PROJECT_METADATA_JSON" ]]; then
    printf '%s\n' "$PROJECT_METADATA_JSON"
    return
  fi

  local query response
  read -r -d '' query <<'EOF' || true
query($owner: String!, $number: Int!) {
  organization(login: $owner) {
    projectV2(number: $number) {
      id
      title
      url
      fields(first: 50) {
        nodes {
          __typename
          ... on ProjectV2FieldCommon {
            id
            name
          }
          ... on ProjectV2SingleSelectField {
            id
            name
            options {
              id
              name
            }
          }
        }
      }
    }
  }
  user(login: $owner) {
    projectV2(number: $number) {
      id
      title
      url
      fields(first: 50) {
        nodes {
          __typename
          ... on ProjectV2FieldCommon {
            id
            name
          }
          ... on ProjectV2SingleSelectField {
            id
            name
            options {
              id
              name
            }
          }
        }
      }
    }
  }
}
EOF

  response="$(gh api graphql -F owner="$PROJECT_OWNER" -F number="$PROJECT_NUMBER" -f query="$query" 2>/dev/null || true)" || \
    fail "unable to load project metadata for owner '$PROJECT_OWNER' and project '$PROJECT_NUMBER'"
  PROJECT_METADATA_JSON="$(
    jq -ce '.data.organization.projectV2 // .data.user.projectV2' <<<"$response"
  )" || fail "project '$PROJECT_NUMBER' was not found for owner '$PROJECT_OWNER'"
  printf '%s\n' "$PROJECT_METADATA_JSON"
}

project_id() {
  project_metadata_json | jq -r '.id'
}

field_id_by_name() {
  local field_name="$1"
  local field_id
  field_id="$(
    project_metadata_json | jq -r --arg field_name "$field_name" '
      .fields.nodes[]
      | select(.name == $field_name)
      | .id
    ' | head -n1
  )"
  [[ -n "$field_id" ]] || fail "field '$field_name' was not found in project '$PROJECT_NUMBER'"
  printf '%s\n' "$field_id"
}

single_select_option_id() {
  local field_name="$1"
  local option_name="$2"
  local option_id
  option_id="$(
    project_metadata_json | jq -r --arg field_name "$field_name" --arg option_name "$option_name" '
      .fields.nodes[]
      | select(.name == $field_name)
      | .options[]
      | select(.name == $option_name)
      | .id
    ' | head -n1
  )"
  [[ -n "$option_id" ]] || fail "option '$option_name' was not found in field '$field_name'"
  printf '%s\n' "$option_id"
}

project_items_json() {
  if [[ -n "$PROJECT_ITEMS_JSON" ]]; then
    printf '%s\n' "$PROJECT_ITEMS_JSON"
    return
  fi

  local query all page node page_items has_next cursor args
  read -r -d '' query <<'EOF' || true
query($owner: String!, $number: Int!, $cursor: String) {
  organization(login: $owner) {
    projectV2(number: $number) {
      items(first: 100, after: $cursor) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          id
          fieldValues(first: 20) {
            nodes {
              __typename
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                optionId
                field {
                  ... on ProjectV2SingleSelectField {
                    id
                    name
                  }
                }
              }
              ... on ProjectV2ItemFieldTextValue {
                text
                field {
                  ... on ProjectV2FieldCommon {
                    id
                    name
                  }
                }
              }
              ... on ProjectV2ItemFieldDateValue {
                date
                field {
                  ... on ProjectV2FieldCommon {
                    id
                    name
                  }
                }
              }
            }
          }
          content {
            __typename
            ... on Issue {
              id
              number
              title
              url
              state
              repository {
                nameWithOwner
              }
            }
          }
        }
      }
    }
  }
  user(login: $owner) {
    projectV2(number: $number) {
      items(first: 100, after: $cursor) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          id
          fieldValues(first: 20) {
            nodes {
              __typename
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                optionId
                field {
                  ... on ProjectV2SingleSelectField {
                    id
                    name
                  }
                }
              }
              ... on ProjectV2ItemFieldTextValue {
                text
                field {
                  ... on ProjectV2FieldCommon {
                    id
                    name
                  }
                }
              }
              ... on ProjectV2ItemFieldDateValue {
                date
                field {
                  ... on ProjectV2FieldCommon {
                    id
                    name
                  }
                }
              }
            }
          }
          content {
            __typename
            ... on Issue {
              id
              number
              title
              url
              state
              repository {
                nameWithOwner
              }
            }
          }
        }
      }
    }
  }
}
EOF

  all='[]'
  cursor=""
  while true; do
    args=(-F owner="$PROJECT_OWNER" -F number="$PROJECT_NUMBER" -f query="$query")
    if [[ -n "$cursor" ]]; then
      args+=(-F cursor="$cursor")
    fi

    page="$(gh api graphql "${args[@]}" 2>/dev/null || true)" || fail "unable to list project items"
    node="$(
      jq -ce '.data.organization.projectV2 // .data.user.projectV2' <<<"$page"
    )" || fail "project '$PROJECT_NUMBER' was not found while listing items"
    page_items="$(jq -c '.items.nodes' <<<"$node")"
    all="$(jq -cs '.[0] + .[1]' <(printf '%s\n' "$all") <(printf '%s\n' "$page_items"))"
    has_next="$(jq -r '.items.pageInfo.hasNextPage' <<<"$node")"
    if [[ "$has_next" != "true" ]]; then
      break
    fi
    cursor="$(jq -r '.items.pageInfo.endCursor' <<<"$node")"
  done

  PROJECT_ITEMS_JSON="$all"
  printf '%s\n' "$PROJECT_ITEMS_JSON"
}

project_item_by_issue_number() {
  local issue_number="$1"
  project_items_json | jq -ce --argjson issue_number "$issue_number" '
    map(select(.content.__typename == "Issue" and .content.number == $issue_number))[0]
  ' || fail "issue #$issue_number is not in project '$PROJECT_NUMBER'"
}

project_item_id_by_issue_number() {
  local issue_number="$1"
  project_item_by_issue_number "$issue_number" | jq -r '.id'
}

issue_url_by_number() {
  local issue_number="$1"
  gh issue view "$issue_number" --repo "$PROJECT_REPO" --json url --jq .url
}

issue_number_from_url() {
  local issue_url="$1"
  gh issue view "$issue_url" --repo "$PROJECT_REPO" --json number --jq .number
}

item_field_single_select_value() {
  local item_json="$1"
  local field_name="$2"
  jq -r --arg field_name "$field_name" '
    .fieldValues.nodes[]
    | select(.field.name == $field_name and .name != null)
    | .name
  ' <<<"$item_json" | head -n1
}

set_item_status() {
  local item_id="$1"
  local status_name="$2"
  gh project item-edit \
    --id "$item_id" \
    --project-id "$(project_id)" \
    --field-id "$(field_id_by_name "$PROJECT_STATUS_FIELD_NAME")" \
    --single-select-option-id "$(single_select_option_id "$PROJECT_STATUS_FIELD_NAME" "$status_name")" \
    >/dev/null
}

set_item_text_field() {
  local item_id="$1"
  local field_name="$2"
  local value="$3"
  gh project item-edit \
    --id "$item_id" \
    --project-id "$(project_id)" \
    --field-id "$(field_id_by_name "$field_name")" \
    --text "$value" \
    >/dev/null
}

set_item_date_field() {
  local item_id="$1"
  local field_name="$2"
  local value="$3"
  gh project item-edit \
    --id "$item_id" \
    --project-id "$(project_id)" \
    --field-id "$(field_id_by_name "$field_name")" \
    --date "$value" \
    >/dev/null
}

comment_on_issue() {
  local issue_number="$1"
  local body="$2"
  [[ -n "$body" ]] || return 0
  gh issue comment "$issue_number" --repo "$PROJECT_REPO" --body "$body" >/dev/null
}

today_utc() {
  date -u +%F
}

agent_name_default() {
  if [[ -n "${AGENT_NAME:-}" ]]; then
    printf '%s\n' "$AGENT_NAME"
    return
  fi
  if [[ -n "${USER:-}" ]]; then
    printf '%s\n' "$USER"
    return
  fi
  printf 'unknown-agent\n'
}
