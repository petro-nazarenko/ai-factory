# Pipeline Reference

## Execution modes

| Mode | Steps | External calls |
|---|---|---|
| `DRY_RUN` | 0 → 3 | None (mock data) |
| `GENERATE_ONLY` | 0 → 3 | Anthropic API only |
| `FULL_PIPELINE` | 0 → 7 | Anthropic + Sheets + email |

Default: `GENERATE_ONLY`.

```bash
bash run_pipeline.sh --dry-run        # DRY_RUN
bash run_pipeline.sh                  # GENERATE_ONLY
bash run_pipeline.sh --full           # FULL_PIPELINE
```

---

## Step-by-step

### Step 0 — Init

Creates the run directory and initialises `status.json` and `logs.txt`.

```
workspace/runs/<RUN_ID>/
  status.json   ← {"step":"init","status":"pending",...}
  logs.txt      ← append-only
```

### Step 1 — Signal mining (`Moneymaker/`)

Sources: HN Algolia, RemoteOK, Reddit (`praw`).  
Each signal carries: `idea`, `score`, `source_url`, `source_company`, `source_author`, `source_platform`, `posted_date`.

Output: `workspace/runs/<RUN_ID>/ideas.json`

### Step 2 — Connector

Filters `ideas.json` to `score >= 7.0` and maps each idea to an AKF prompt.

Output: `workspace/runs/<RUN_ID>/connector.json`

### Step 3 — AKF validation (`ai-knowledge-filler/`)

Enforces YAML frontmatter schema. Error codes E001–E008, max 2 retries per field.  
Ideas that fail after retries are logged and skipped.

Output: `workspace/runs/<RUN_ID>/validated/idea_N.md`

### Step 4 — Lead extraction

Reads validated `.md` files and builds `workspace/leads/leads.json`.

### Step 5 — Client finder

Supplements leads with additional metadata via `workspace/client_finder.py`.

### Step 6 — Match engine

Scores each `(idea, lead)` pair using keyword overlap + LLM fit score.

```
idea.domain     ↔  lead.pain keywords
idea.target_user ↔  lead.company profile
idea.tags       ↔  lead.stack
```

Output: `workspace/matches/matches.json`

### Step 7 — Offer generator

Generates a personalised cold-outreach draft per match, referencing the exact source post.

Output: `workspace/offers/offer_N.md`

### Step 8 — Send + track (TODO)

Sends via email / Upwork DM, logs to Google Sheets, schedules follow-ups at day 3 / 7 / 14.

---

## Run directory layout

```
workspace/runs/<RUN_ID>/
├── ideas.json          ← Moneymaker output (all signals)
├── connector.json      ← filtered + formatted for AKF
├── validated/
│   └── idea_N.md       ← schema-valid idea with lead metadata
├── logs.txt            ← append-only, one line per event
├── status.json         ← current step + status
└── report.json         ← final summary (ideas_mined, passed, validated, ...)
```

## Log format

```
[TIMESTAMP] [RUN_ID] [STEP] [STATUS] message
```

Example:

```
[2026-04-04T22:00:22Z] [run_20260404_220006] [VALIDATION] [SUCCESS] validated/ populated
```

## Error handling

| Error | Action |
|---|---|
| AKF validation field error | Apply correction, retry (max 2). Skip idea on second failure. |
| CLI non-zero exit | Log + retry once. Stop pipeline on second failure. |
| `ideas.json` missing | Stop immediately. |
| All ideas filtered (score < 7.0) | Log warning. Stop. Increase `--limit` or broaden sources. |
