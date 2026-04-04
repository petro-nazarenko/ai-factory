#!/usr/bin/env bash
# Moneymaker v5 — smoke test
# Usage: bash scripts/smoke_test.sh 2>&1 | tee smoke_output.txt

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "Installing dependencies..."
pip install -r requirements.txt -q

PASS=0; FAIL=0
GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'; BOLD='\033[1m'

ok()   { echo -e "${GREEN}✓${NC} $1"; PASS=$((PASS+1)); }
fail() { echo -e "${RED}✗${NC} $1"; FAIL=$((FAIL+1)); }
h()    { echo -e "\n${BOLD}── $1 ──${NC}"; }

# ── 1. Python imports ────────────────────────────────────────────────────────
h "1. Python imports"

python -c "from src.config import settings; print('  DATABASE_URL:', settings.database_url[:30]+'...')" \
  && ok "src.config" || fail "src.config"

python -c "from src.models import RejectReason; r=list(RejectReason); print('  reasons:', [x.value for x in r]); assert len(r)==5" \
  && ok "src.models.RejectReason (5 values)" || fail "src.models.RejectReason"

python -c "from core.schema import RunRecord, IdeaRecord, MetricRecord, WeightRecord; print('  ORM tables: runs, ideas, metrics, weights')" \
  && ok "core.schema ORM" || fail "core.schema ORM"

python -c "from core.reward import compute_reward, update_weights; r=compute_reward({'payments':1,'mrr':49}); print('  reward(1 payment, mrr=49):', r)" \
  && ok "core.reward" || fail "core.reward"

python -c "from workers.celery_app import app; print('  broker:', app.conf.broker_url)" \
  && ok "workers.celery_app" || fail "workers.celery_app"

python -c "from workers.tasks import mine_signals, generate_ideas, score_and_filter, build_and_deploy, distribute_best, trigger_cycle; print('  tasks:', 6)" \
  && ok "workers.tasks (6 tasks)" || fail "workers.tasks"

python -c "from api.main import app; print('  routes:', len(app.routes))" \
  && ok "api.main FastAPI" || fail "api.main FastAPI"

# ── 2. Dry-run pipeline ──────────────────────────────────────────────────────
h "2. Dry-run pipeline (no API calls)"

python main.py --dry-run --sources reddit --limit 3 --no-distribute --no-fulfill \
  --output /dev/null \
  && ok "main.py --dry-run completed" || fail "main.py --dry-run failed"

# ── 3. RejectReason enum completeness ────────────────────────────────────────
h "3. RejectReason enum vs money_filter prompt"

python - <<'EOF'
from src.models import RejectReason
import src.money_filter as mf
prompt = mf._SYSTEM_PROMPT
missing = [r.value for r in RejectReason if r.value not in prompt]
if missing:
    print(f"  MISSING in prompt: {missing}")
    raise SystemExit(1)
print(f"  All {len(list(RejectReason))} values present in prompt")
EOF
  && ok "All RejectReason values in AI prompt" || fail "RejectReason values missing from prompt"

# ── 4. docker compose config ─────────────────────────────────────────────────
h "4. Docker Compose validation"

docker compose config --quiet \
  && ok "docker-compose.yml valid" || fail "docker-compose.yml invalid"

# ── 5. Docker build ───────────────────────────────────────────────────────────
h "5. Docker build"

docker compose build --quiet \
  && ok "Docker image built" || fail "Docker build failed"

# ── 6. Bring up stack ────────────────────────────────────────────────────────
h "6. docker compose up"

docker compose up -d
sleep 8  # wait for healthchecks

# ── 7. Health checks ─────────────────────────────────────────────────────────
h "7. Service health checks"

curl -sf http://localhost:8000/healthz | python -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='ok'" \
  && ok "GET /healthz → 200 ok" || fail "GET /healthz failed"

docker compose ps --format json | python -c "
import sys, json
for line in sys.stdin:
    s = json.loads(line.strip())
    name = s.get('Name','?')
    state = s.get('State','?')
    health = s.get('Health','')
    status = f'{state}/{health}' if health else state
    print(f'  {name}: {status}')
" && ok "Services listed" || fail "docker compose ps failed"

# ── 8. API endpoints ─────────────────────────────────────────────────────────
h "8. API endpoints"

curl -sf http://localhost:8000/metrics | grep -q "http_requests_total" \
  && ok "GET /metrics → Prometheus output" || fail "GET /metrics failed"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/v1/cycles/start \
  -H "Content-Type: application/json" \
  -d '{"sources":["reddit"],"limit":3}')
[ "$STATUS" = "200" ] \
  && ok "POST /api/v1/cycles/start → 200" || fail "POST /api/v1/cycles/start → $STATUS"

curl -sf http://localhost:8000/api/v1/weights | python -c "import sys,json; d=json.load(sys.stdin); print(f'  weights: {len(d)} features')" \
  && ok "GET /api/v1/weights → weights list" || fail "GET /api/v1/weights failed"

curl -sf http://localhost:8000/api/v1/ideas | python -c "import sys,json; d=json.load(sys.stdin); print(f'  ideas: {len(d)} rows')" \
  && ok "GET /api/v1/ideas → ideas list" || fail "GET /api/v1/ideas failed"

# ── 9. Celery worker ─────────────────────────────────────────────────────────
h "9. Celery worker"

docker compose exec worker celery -A workers.celery_app inspect ping --timeout 5 \
  && ok "Celery worker responds to ping" || fail "Celery worker not responding"

docker compose exec worker celery -A workers.celery_app inspect registered --timeout 5 \
  | grep -q "mine_signals" \
  && ok "Tasks registered: mine_signals detected" || fail "Tasks not registered"

# ── Summary ───────────────────────────────────────────────────────────────────
h "Summary"
TOTAL=$((PASS + FAIL))
echo -e "${BOLD}${PASS}/${TOTAL} passed${NC}"
[ "$FAIL" -eq 0 ] && echo -e "${GREEN}ALL TESTS PASSED${NC}" || echo -e "${RED}${FAIL} FAILED${NC}"
exit "$FAIL"
