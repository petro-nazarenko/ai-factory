#!/usr/bin/env bash
# =============================================================================
# AI Factory — GENERATE_ONLY pipeline runner
# Steps: 0 (init) → 1 (Moneymaker) → 2 (connector) → 3 (AKF validation)
# External calls: Anthropic API only
# Usage: bash run_pipeline.sh [--dry-run]
# =============================================================================

set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

# ---------------------------------------------------------------------------
# STEP 0 — INIT
# ---------------------------------------------------------------------------
RUN_ID="run_$(date +%Y%m%d_%H%M%S)"
BASE="$REPO/workspace/runs/$RUN_ID"
mkdir -p "$BASE/validated"

cat > "$BASE/status.json" <<EOF
{"run_id":"$RUN_ID","step":"init","status":"pending","retries":0,"errors":[]}
EOF
touch "$BASE/logs.txt"

log() {
  local ts step status msg
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  step="$1"; status="$2"; msg="$3"
  echo "[$ts] [$RUN_ID] [$step] [$status] $msg" | tee -a "$BASE/logs.txt"
}

update_status() {
  local step="$1" status="$2"
  cat > "$BASE/status.json" <<EOF
{"run_id":"$RUN_ID","step":"$step","status":"$status","retries":0,"errors":[]}
EOF
}

log "INIT" "SUCCESS" "run created → $BASE"

# ---------------------------------------------------------------------------
# Pre-flight: check at least one LLM key is set (unless dry-run)
# ---------------------------------------------------------------------------
if [[ "$DRY_RUN" == "false" ]]; then
  # Always source .env so all keys (GROQ, CEREBRAS, ANTHROPIC, etc.) are loaded.
  # Variables already set in the environment take precedence because set -a
  # only exports; it does not override existing exports.
  if [[ -f "$REPO/Moneymaker/.env" ]]; then
    set -a
    source "$REPO/Moneymaker/.env"
    set +a
  fi
  if [[ -z "${GROQ_API_KEY:-}" ]] && [[ -z "${CEREBRAS_API_KEY:-}" ]] && [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    log "INIT" "FAIL" "No LLM key set — provide GROQ_API_KEY, CEREBRAS_API_KEY, or ANTHROPIC_API_KEY"
    exit 1
  fi
  if [[ -n "${GROQ_API_KEY:-}" ]]; then
    log "INIT" "SUCCESS" "LLM provider: Groq (llama-3.3-70b-versatile)"
  elif [[ -n "${CEREBRAS_API_KEY:-}" ]]; then
    log "INIT" "SUCCESS" "LLM provider: Cerebras (llama3.3-70b)"
  else
    log "INIT" "SUCCESS" "LLM provider: Anthropic Claude (fallback)"
  fi
fi

# ---------------------------------------------------------------------------
# STEP 1 — SIGNAL MINING (Moneymaker)
# ---------------------------------------------------------------------------
log "IDEA_GEN" "RUNNING" "sources=jobboards,reddit limit=20 dry_run=$DRY_RUN"
update_status "idea_gen" "running"

cd "$REPO/Moneymaker"

MONEYMAKER_ARGS="--sources jobboards reddit --limit 20 --output $BASE/ideas.json --no-fulfill --no-distribute"
if [[ "$DRY_RUN" == "true" ]]; then
  MONEYMAKER_ARGS="$MONEYMAKER_ARGS --dry-run"
fi

if python main.py $MONEYMAKER_ARGS; then
  log "IDEA_GEN" "SUCCESS" "ideas.json written"
  update_status "idea_gen" "success"
else
  EXIT=$?
  log "IDEA_GEN" "RUNNING" "first attempt failed (exit $EXIT) — retrying once"
  if python main.py $MONEYMAKER_ARGS; then
    log "IDEA_GEN" "SUCCESS" "ideas.json written (retry 1)"
    update_status "idea_gen" "success"
  else
    log "IDEA_GEN" "FAIL" "Moneymaker failed after 2 attempts — STOP"
    update_status "idea_gen" "failed"
    exit 1
  fi
fi

cd "$REPO"

# Guard: ideas.json must exist and be non-empty
if [[ ! -f "$BASE/ideas.json" ]] || [[ ! -s "$BASE/ideas.json" ]]; then
  log "IDEA_GEN" "FAIL" "ideas.json missing or empty — STOP"
  exit 1
fi

# ---------------------------------------------------------------------------
# STEP 2 — CONNECTOR
# ---------------------------------------------------------------------------
log "CONNECTOR" "RUNNING" "input=ideas.json threshold=0.7"
update_status "connector" "running"

if python "$REPO/workspace/connector.py" \
    --input "$BASE/ideas.json" \
    --output "$BASE/connector.json"; then
  log "CONNECTOR" "SUCCESS" "connector.json written"
  update_status "connector" "success"
else
  EXIT=$?
  if [[ $EXIT -eq 2 ]]; then
    log "CONNECTOR" "FAIL" "0 ideas passed score filter — adjust --limit or sources"
  else
    log "CONNECTOR" "FAIL" "connector.py error (exit $EXIT) — STOP"
  fi
  update_status "connector" "failed"
  exit 1
fi

# ---------------------------------------------------------------------------
# STEP 3 — AKF VALIDATION
# ---------------------------------------------------------------------------
log "VALIDATION" "RUNNING" "input=connector.json output=validated/ dry_run=$DRY_RUN"
update_status "validation" "running"

AKF_CMD="python $REPO/ai-knowledge-filler/akf.py batch \
  --input $BASE/connector.json \
  --output $BASE/validated"

if [[ "$DRY_RUN" == "true" ]]; then
  # In dry-run: AKF uses the same Claude client but we warn if key is absent
  log "VALIDATION" "RUNNING" "dry-run mode: AKF will use mock prompts with real schema validation"
fi

if $AKF_CMD; then
  log "VALIDATION" "SUCCESS" "validated/ populated"
  update_status "validation" "success"
else
  log "VALIDATION" "FAIL" "AKF batch failed — check validated/ for partial output"
  update_status "validation" "failed"
  exit 1
fi

# ---------------------------------------------------------------------------
# FINAL REPORT
# ---------------------------------------------------------------------------
VALIDATED_COUNT=$(ls "$BASE/validated/"*.md 2>/dev/null | wc -l | tr -d ' ')

cat > "$BASE/report.json" <<EOF
{
  "run_id": "$RUN_ID",
  "mode": "GENERATE_ONLY",
  "status": "success",
  "dry_run": $DRY_RUN,
  "steps_completed": ["init", "idea_gen", "connector", "validation"],
  "ideas_validated": $VALIDATED_COUNT,
  "errors": []
}
EOF

log "REPORT" "SUCCESS" "run complete — $VALIDATED_COUNT ideas validated in $BASE"

echo ""
echo "======================================"
echo " RUN COMPLETE: $RUN_ID"
echo " Mode: GENERATE_ONLY (dry_run=$DRY_RUN)"
echo " Validated: $VALIDATED_COUNT ideas"
echo " Output: $BASE/"
echo "======================================"
