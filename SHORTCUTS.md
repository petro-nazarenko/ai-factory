# AI Factory — Shortcuts & Cheatsheet

Quick-reference for the most common commands.

---

## Local pipeline

```bash
# Dry run — no external API calls, uses mock data
bash run_pipeline.sh --dry-run

# Live run — requires at least one LLM key in Moneymaker/.env
bash run_pipeline.sh
```

### Environment setup (first time)

```bash
cp Moneymaker/.env.example Moneymaker/.env
# then set one of:
echo "GROQ_API_KEY=gsk_..."        >> Moneymaker/.env
echo "CEREBRAS_API_KEY=..."        >> Moneymaker/.env
echo "ANTHROPIC_API_KEY=sk-ant-..." >> Moneymaker/.env

pip install -r requirements.txt
```

---

## Moneymaker (signal mining)

```bash
cd Moneymaker

# All sources, 20 signals, dry run
python main.py --sources jobboards reddit --limit 20 --dry-run

# Job boards only, write to file
python main.py --sources jobboards --limit 10 --output /tmp/ideas.json

# Reddit only, skip fulfillment and distribution
python main.py --sources reddit --limit 15 --no-fulfill --no-distribute
```

---

## Connector (score filter)

```bash
# Filter ideas.json → connector.json  (passes score ≥ 7.0)
python workspace/connector.py \
  --input  workspace/runs/<RUN_ID>/ideas.json \
  --output workspace/runs/<RUN_ID>/connector.json
```

---

## AKF validation

```bash
cd ai-knowledge-filler

# Validate a single batch
python akf.py batch \
  --input  ../workspace/runs/<RUN_ID>/connector.json \
  --output ../workspace/runs/<RUN_ID>/validated
```

---

## REST API (Railway)

Base URL: `https://web-production-61489.up.railway.app`  
Auth header: `X-API-Key: <key>`

```bash
API=https://web-production-61489.up.railway.app
KEY=<your-api-key>

# Start a dry run
curl -s -X POST "$API/run?dry_run=true" -H "X-API-Key: $KEY" | jq .

# Start a live run
curl -s -X POST "$API/run" -H "X-API-Key: $KEY" | jq .

# Check run status + validated ideas
curl -s "$API/runs/<RUN_ID>" -H "X-API-Key: $KEY" | jq .

# Stream logs
curl -s "$API/runs/<RUN_ID>/logs" -H "X-API-Key: $KEY"

# List all runs
curl -s "$API/runs" -H "X-API-Key: $KEY" | jq .
```

---

## Output locations

```
workspace/runs/<RUN_ID>/
  ideas.json       ← raw signals from Moneymaker
  connector.json   ← filtered prompts (score ≥ 7.0)
  validated/       ← schema-valid .md files (one per idea)
  logs.txt         ← append-only run log
  status.json      ← current step + status
  report.json      ← final summary
```

---

## Log format

```
[2026-04-04T22:00:22Z] [run_20260404_220006] [VALIDATION] [SUCCESS] validated/ populated
```

Fields: `[timestamp] [run_id] [step] [status] message`

---

## Key environment variables

| Variable | Used by | Purpose |
|---|---|---|
| `GROQ_API_KEY` | Moneymaker, AKF | Primary LLM (llama-3.3-70b) |
| `CEREBRAS_API_KEY` | Moneymaker, AKF | Secondary LLM (llama3.3-70b) |
| `ANTHROPIC_API_KEY` | Moneymaker, AKF | Fallback LLM (Claude) |
| `API_KEY` | ai-factory-api | REST API authentication |
| `SPREADSHEET_ID` | Agent-Guidelines | Google Sheets target |
| `TARGET_EMAIL` | Agent-Guidelines | Outreach email address |
