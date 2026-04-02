#!/bin/bash
# Deterministic model pricing collector
# Fetches current pricing from OpenRouter API (public, no auth needed)
# and updates model-pricing.json with actual costs.
#
# Run daily via cron or launchd. Zero token cost — pure HTTP.
#
# Usage: ./collect-model-pricing.sh [output-file]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT="${1:-$SCRIPT_DIR/model-pricing.json}"
TEMP_FILE="/tmp/openrouter-models-$$.json"
LOG_FILE="$SCRIPT_DIR/logs/pricing-collector.log"

mkdir -p "$(dirname "$LOG_FILE")"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG_FILE"; }

log "Starting pricing collection"

# Fetch model list from OpenRouter (public endpoint, no API key)
HTTP_CODE=$(curl -sL -w "%{http_code}" \
  -o "$TEMP_FILE" \
  "https://openrouter.ai/api/v1/models" \
  --max-time 30 2>/dev/null || echo "000")

if [ "$HTTP_CODE" != "200" ]; then
  log "ERROR: OpenRouter API returned $HTTP_CODE — keeping existing pricing"
  rm -f "$TEMP_FILE"
  exit 1
fi

# Extract pricing for models we care about
python3 - "$TEMP_FILE" "$OUTPUT" << 'PYEOF'
import json
import sys
from pathlib import Path

temp_file = sys.argv[1]
output_path = Path(sys.argv[2])

with open(output_path) as f:
    config = json.load(f)

# Load OpenRouter data
with open(temp_file) as f:
    api_data = json.load(f)

# Models we track
tracked_models = set()
for tier_data in config["tiers"].values():
    for m in tier_data["models"]:
        if not m.endswith("/*"):  # Skip wildcard entries
            tracked_models.add(m)

# Build pricing map
pricing = {}
for model in api_data.get("data", []):
    model_id = model.get("id", "")
    if model_id in tracked_models:
        p = model.get("pricing", {})
        pricing[model_id] = {
            "input_per_1m": round(float(p.get("prompt", 0)) * 1_000_000, 4),
            "output_per_1m": round(float(p.get("completion", 0)) * 1_000_000, 4),
            "context_length": model.get("context_length", 0)
        }

# Update config
from datetime import datetime, timezone
config["_meta"]["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
config["_meta"]["models_found"] = len(pricing)
config["_meta"]["models_tracked"] = len(tracked_models)
config["actual_pricing"] = pricing

# Re-classify models into tiers based on actual pricing
for tier_name, tier_data in config["tiers"].items():
    max_in = tier_data["max_input_per_1m"]
    max_out = tier_data["max_output_per_1m"]
    for model_id, p in pricing.items():
        if model_id in tier_data["models"]:
            # Verify the model is still in the right tier
            if p["input_per_1m"] > max_in or p["output_per_1m"] > max_out:
                if "_warnings" not in config:
                    config["_warnings"] = []
                config["_warnings"].append(
                    f"{model_id} exceeds {tier_name} tier limits: "
                    f"${p['input_per_1m']}/1M in, ${p['output_per_1m']}/1M out "
                    f"(max: ${max_in}/{max_out})"
                )

with open(output_path, "w") as f:
    json.dump(config, f, indent=2)
    f.write("\n")

print(f"Updated {output_path}: {len(pricing)} models priced, {len(config.get('_warnings', []))} warnings")
PYEOF

rm -f "$TEMP_FILE"
log "Pricing collection complete"
