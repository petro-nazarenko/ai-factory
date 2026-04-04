# AI FACTORY — CLAUDE OPERATOR SPEC

## CORE PRINCIPLE

This repo is self-orchestrating via this file.
No external framework. File-based. Deterministic.

Modules:
- `Moneymaker/`       — signal mining + idea generation
- `ai-knowledge-filler/` — validation + structuring (AKF)
- `Agent-Guidelines-for-Upwork-Learning-Projects/` — execution (Sheets, email, PDF)

---

## RUN IDENTIFICATION

Format: `RUN_ID=run_YYYYMMDD_HHMMSS`

Every run gets a unique RUN_ID used in ALL logs, files, outputs.

---

## DIRECTORY STRUCTURE

```
workspace/runs/$RUN_ID/
  ideas.json        ← Moneymaker output
  connector.json    ← adapted for AKF input
  validated.md      ← AKF output
  report.json       ← final run report
  logs.txt          ← append-only log
  status.json       ← current state
```

---

## LOG FORMAT

```
[TIMESTAMP] [RUN_ID] [STEP] [STATUS] message
```

Append ALL logs to `workspace/runs/$RUN_ID/logs.txt`. No silent steps.

---

## STATUS SCHEMA

```json
{
  "run_id": "run_20260403_142501",
  "step": "validation",
  "status": "running",
  "retries": 0,
  "errors": []
}
```

Values: `pending` | `running` | `success` | `failed`

---

## PIPELINE (STRICT ORDER)

### STEP 0 — INIT

```bash
RUN_ID=run_$(date +%Y%m%d_%H%M%S)
BASE=workspace/runs/$RUN_ID
mkdir -p $BASE
echo '{"run_id":"'$RUN_ID'","step":"init","status":"pending","retries":0,"errors":[]}' > $BASE/status.json
echo "" > $BASE/logs.txt
```

Log: `[INIT] run created`

---

### STEP 1 — SIGNAL MINING (Moneymaker)

```bash
cd Moneymaker
python main.py --sources jobboards reddit --limit 20 --output ../$BASE/ideas.json
```

Sources:
- `jobboards` — Upwork RSS (primary)
- `reddit` — pain signals (secondary)
- `--dry-run` — mock data, no external calls

Log: `[IDEA_GEN] running → success/fail`

Output contract (`ideas.json`):
```json
[
  {
    "idea": "string",
    "score": 0.0
  }
]
```

Only ideas that pass Money Filter reach this file:
- existing spend behavior ✅
- clear buyer ✅
- MVP ≤ 24h ✅
- sellable without brand ✅

---

### STEP 2 — CONNECTOR (ideas.json → AKF)

```bash
python workspace/connector.py \
  --input $BASE/ideas.json \
  --output $BASE/connector.json
```

`connector.py` maps each idea into AKF prompt format:

```json
[
  {
    "prompt": "Create a solution spec: <idea text>",
    "score": 0.85
  }
]
```

Filter: only ideas with `score >= 0.7` pass to AKF.

Log: `[CONNECTOR] N ideas → M passed filter`

---

### STEP 3 — STRUCTURING + VALIDATION (AKF)

```bash
cd ai-knowledge-filler

for prompt in connector.json:
    akf generate "<prompt>" --output ../$BASE/validated/
```

AKF schema enforced:
```
title: string
type: guide | reference | checklist
domain: automation | maritime | api-design | devops
level: beginner | intermediate | advanced
status: active
tags: [string] (min 3)
created: ISO 8601
updated: ISO 8601
```

On validation error:
1. AKF Error Normalizer converts typed error → correction instruction
2. Retry (max 2 per field)
3. Same field fails twice → ABORT that idea, log, continue next

Log: `[VALIDATION] idea_N → success/fail/abort`

---

### STEP 4 — STORAGE (Google Sheets)

```bash
cd Agent-Guidelines-for-Upwork-Learning-Projects
python -m src.cli sheets-write \
  -s $SPREADSHEET_ID \
  -r A1 \
  --values "$(python workspace/to_csv.py $BASE/validated/)"
```

Columns: `run_id | idea | score | domain | status | created`

Log: `[STORAGE] N rows written`

---

### STEP 5 — EXECUTION (Email outreach)

Only after validation passed.

```bash
cd Agent-Guidelines-for-Upwork-Learning-Projects
python -m src.cli email-send \
  -t "$TARGET_EMAIL" \
  -s "AI automation solution — $(date +%Y-%m-%d)" \
  -b "$(cat $BASE/validated/*.md | head -1)"
```

Log: `[EXECUTION] email sent → $TARGET_EMAIL`

---

## EXECUTION MODES

| Mode | Steps | External calls |
|---|---|---|
| `DRY_RUN` | 0→3 | none (mock data) |
| `GENERATE_ONLY` | 0→3 | Anthropic API only |
| `FULL_PIPELINE` | 0→5 | Anthropic + Sheets + email |

Default: `GENERATE_ONLY`

---

## ERROR HANDLING

### Validation error (AKF)
1. Read typed error code (E001–E008)
2. Apply correction via Error Normalizer
3. Retry (max 2 per field)
4. Same field fails twice → skip idea, log error, continue

### CLI error
1. Log command + exit code
2. Retry once
3. Fails again → STOP pipeline

### Missing ideas.json
→ STOP. Do not proceed without Moneymaker output.

### score < 0.7 (all ideas filtered)
→ Log warning. Do not proceed. Adjust `--limit` or sources.

---

## REPORT SCHEMA

```json
{
  "run_id": "run_20260403_142501",
  "mode": "GENERATE_ONLY",
  "status": "success",
  "ideas_mined": 20,
  "ideas_passed_filter": 5,
  "ideas_validated": 4,
  "ideas_failed": 1,
  "steps_completed": ["init", "idea_gen", "connector", "validation"],
  "errors": [],
  "duration_seconds": 38
}
```

---

## HARD CONSTRAINTS

- NEVER skip validation
- NEVER execute (email/sheets) on unvalidated data
- NEVER proceed if ideas.json missing or empty
- NEVER exceed 2 retries per field
- NEVER modify Moneymaker or AKF core logic

---

## SUCCESS CRITERIA

```
✔ workspace/runs/$RUN_ID/ exists
✔ logs.txt populated
✔ status.json → "status": "success"
✔ validated/ contains ≥ 1 schema-correct file
```

---

## PIPELINE 3 — MATCH → OFFER → SEND (TODO)

Full venture builder loop:

```
Signals → Ideas → Filter → Validation
        → Leads (source_url, company, author)
        → MATCH  (idea.domain ↔ lead.pain → fit score)
        → OFFER  (personalized message per company per pain)
        → SEND   (email / Upwork / LinkedIn DM)
        → TRACK  (Sheets: sent, opened, replied, closed)
        → $
```

### STEP 6 — MATCHING ENGINE

Input: `validated/*.md` + `leads/leads.json`

Match criteria:
- `idea.domain` ↔ `lead.pain` keywords
- `idea.target_user` ↔ `lead.company` profile
- `idea.tags` ↔ `lead.stack`

Output: `workspace/matches/matches.json`

```json
[
  {
    "idea": "SalesAI",
    "lead_company": "PBS",
    "lead_url": "https://news.ycombinator.com/item?id=...",
    "lead_contact": "user@company.com",
    "fit_score": 8.5,
    "match_reason": "PBS hiring SDRs → SalesAI solves SDR assessment"
  }
]
```

---

### STEP 7 — OFFER GENERATOR

Input: `matches.json`

For each match → generate personalized outreach:
- reference their specific pain from HN post
- show relevant solution (validated idea)
- include demo link if deployed

Output: `workspace/offers/offer_N.md`

---

### STEP 8 — ACTION LAYER

Send via:
- Email → `Agent-Guidelines/email-send`
- Track in Google Sheets → `Agent-Guidelines/sheets-write`
- Follow-up schedule: day 3, day 7, day 14

---

## SYSTEM ARCHITECTURE

```
ai-factory (orchestrator)
├── Moneymaker/          — signal mining
├── ai-knowledge-filler/ — validation + structuring
├── workspace/
│   ├── llm_router.py    — multi-provider LLM routing
│   ├── connector.py     — ideas → AKF format
│   ├── client_finder.py — lead discovery
│   ├── runs/            — all pipeline outputs
│   ├── leads/           — discovered leads
│   ├── matches/         — idea ↔ lead matches (TODO)
│   └── offers/          — generated outreach (TODO)
├── ai-factory-api/      — FastAPI gateway (Railway)
└── Agent-Guidelines/    — execution layer
```

---

## OPERATOR MINDSET

You are running jobs, not answering questions.

```
Correctness > speed
Determinism > creativity
Execution > explanation
```

NO silent failures. NO skipped steps. NO invalid outputs.
