<p align="center">
  <img src="logo.svg" width="80" />
</p>

<h1 align="center">AI Factory</h1>

<p align="center">
  <em>From market signals to closed deals. Automatically.</em>
</p>

<p align="center">
  <a href="https://github.com/petro-nazarenko/ai-factory/actions/workflows/ci.yml">
    <img src="https://github.com/petro-nazarenko/ai-factory/actions/workflows/ci.yml/badge.svg" alt="CI" />
  </a>
  <img src="https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white" alt="Python 3.12" />
  <img src="https://img.shields.io/badge/deployed_on-Railway-0B0D0E?logo=railway&logoColor=white" alt="Railway" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License" />
  <img src="https://img.shields.io/badge/version-0.3.0-informational" alt="v0.3.0" />
</p>

---

## What it does

AI Factory scans job boards and Reddit for companies expressing specific pain — hiring posts, tool requests, workflow complaints. It converts those signals into validated product ideas, tags each idea with the exact company and contact that created the signal, then matches ideas to leads, generates personalized outreach, and tracks the result. The output is not a list of ideas — it is a prioritized pipeline of real companies with real problems and a ready draft of why you should talk to them.

---

## How it works

```
HN / RemoteOK / Reddit
        │
        ▼
  [1] SIGNAL MINING       — extract pain, score intensity, capture source metadata
        │                   (company, author, url, post date)
        ▼
  [2] IDEA GENERATION     — LLM converts signal → MVPPlan (problem / solution / revenue)
        │
        ▼
  [3] MONEY FILTER        — drop ideas without existing spend, clear buyer, 24h MVP
        │
        ▼
  [4] VALIDATION (AKF)    — enforce schema, retry on error, write structured .md
        │                   each file carries source_url + source_company + source_author
        ▼
  [5] LEAD EXTRACTION     — validated ideas become qualified leads
        │
        ▼
  [6] MATCH               — idea.domain ↔ lead.pain  (fit score)
        │                   (workspace/matcher.py — keyword + LLM scoring)
        ▼
  [7] OFFER GENERATION    — personalized message referencing their exact post
        │                   (workspace/offer_generator.py)
        ▼
  [8] SEND + TRACK        — email / Upwork / Sheets log                 ← in spec
        │
        ▼
        $
```

---

## Status

| Step | Component | Status |
|---|---|---|
| Signal mining (HN + RemoteOK) | `Moneymaker/` | ✅ |
| Idea generation + money filter | `Moneymaker/` | ✅ |
| AKF schema validation | `ai-knowledge-filler/` | ✅ |
| Lead metadata on every idea | frontmatter fields | ✅ |
| REST API (Railway) | `ai-factory-api/` | ✅ |
| Match engine | `workspace/matcher.py` | ✅ |
| Offer generator | `workspace/offer_generator.py` | ✅ |
| Send + track | Pipeline 3 | 🔲 |

---

## Stack

| Layer | Technology |
|---|---|
| Signal mining | Python, httpx, praw (Reddit), HN Algolia API |
| LLM routing | Groq (llama-3.3-70b) → Cerebras → Anthropic (fallback) |
| Validation | Custom schema validator (E001–E008), YAML frontmatter |
| API | FastAPI, uvicorn, Railway |
| Execution | gspread (Sheets), imapclient (email) |
| Config | pydantic-settings, python-dotenv |

The LLM router tracks TPM/TPD limits and fails over automatically on 429s.

---

## API

Deployed at `https://web-production-61489.up.railway.app`. Auth via `X-API-Key` header.

See [`docs/api.md`](docs/api.md) for the full reference.

```bash
# Start a pipeline run
POST /run?dry_run=true
X-API-Key: <key>

# Get run status + validated ideas
GET /runs/{run_id}
X-API-Key: <key>

# Stream logs
GET /runs/{run_id}/logs
X-API-Key: <key>

# List all runs
GET /runs
X-API-Key: <key>
```

---

## Run locally

```bash
# Requires at least one LLM key
cp Moneymaker/.env.example Moneymaker/.env
echo "GROQ_API_KEY=your_key" >> Moneymaker/.env

pip install -r requirements.txt

# Dry run — no external calls, mock data
bash run_pipeline.sh --dry-run

# Live run
bash run_pipeline.sh
```

Results land in `workspace/runs/<RUN_ID>/`.

---

## Output format

Each validated idea is a Markdown file with YAML frontmatter:

```yaml
---
title: "SDR Assessment Automation Tool"
type: guide
domain: automation
level: intermediate
status: active
tags: [sales, automation, ai, assessment]
created: "2026-04-04T22:00:00Z"
updated: "2026-04-04T22:00:00Z"
source_url: "https://news.ycombinator.com/item?id=43512345"
source_company: "Acme Sales Inc"
source_author: "acme_cto"
source_platform: "jobboards"
posted_date: "2026-04-01T09:15:00Z"
---

## Problem
## Target User
## Solution
## Revenue Model
## MVP Format
## Estimated Build Time
## Validation Steps
## Tech Stack
```

---

## Project structure

```
ai-factory/
├── run_pipeline.sh                        ← pipeline entry point
├── ai-factory-api/main.py                 ← FastAPI gateway (Railway)
├── Moneymaker/                            ← steps 1–3: mining, ideas, filter
│   ├── main.py
│   └── src/
│       ├── signal_miner/jobboards.py      ← HN + RemoteOK, captures lead metadata
│       ├── signal_miner/reddit.py
│       ├── idea_generator.py
│       ├── money_filter.py
│       └── models.py                      ← PainSignal with source fields
├── workspace/
│   ├── llm_router.py                      ← unified LLM routing + fallback
│   ├── connector.py                       ← ideas.json → connector.json (score ≥ 7.0)
│   ├── matcher.py                         ← step 6: idea ↔ lead fit scoring
│   ├── offer_generator.py                 ← step 7: personalized cold outreach
│   ├── client_finder.py                   ← standalone lead scanner
│   ├── run_utils.py                       ← shared pipeline utilities
│   ├── tests/                             ← pytest coverage for workspace scripts
│   ├── leads/leads.json
│   └── runs/<RUN_ID>/
│       ├── ideas.json
│       ├── connector.json
│       ├── validated/idea_N.md
│       ├── logs.txt
│       ├── status.json
│       └── report.json
├── ai-knowledge-filler/                   ← schema validation + lead metadata injection
├── Agent-Guidelines-for-Upwork-Learning-Projects/  ← Sheets + email execution
├── docs/                                  ← project documentation
└── requirements.txt
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [ai-knowledge-filler/LICENSE](ai-knowledge-filler/LICENSE).
