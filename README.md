![AI Factory](logo.svg)

# AI Factory — B2B Opportunity Mining & Deal Generation System

![Python](https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Railway](https://img.shields.io/badge/deployed_on-Railway-0B0D0E?logo=railway&logoColor=white)
![Last Commit](https://img.shields.io/github/last-commit/petro-nazarenko/ai-factory?color=informational)
![Stars](https://img.shields.io/github/stars/petro-nazarenko/ai-factory?style=social)

**From market signals to closed deals. Automatically.**

---

## What it does

AI Factory scans job boards and Reddit for companies expressing specific pain — hiring posts, tool requests, workflow complaints. It converts those signals into validated product ideas, tags each idea with the exact company and contact that created the signal, then (in Pipeline 3) matches ideas to leads, generates personalized outreach, and tracks the result. The output is not a list of ideas. It is a prioritized pipeline of real companies with real problems and a ready draft of why you should talk to them.

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
  [6] MATCH ──────────────── idea.domain ↔ lead.pain  (fit score)     ← TODO
        │
        ▼
  [7] OFFER GENERATION ── personalized message referencing their exact post  ← TODO
        │
        ▼
  [8] SEND + TRACK ─────── email / Upwork / Sheets log                 ← TODO
        │
        ▼
        $
```

---

## Current status

What works end-to-end today (deployed on Railway):

| Step | Status | Notes |
|---|---|---|
| Signal mining (HN + RemoteOK) | ✅ | Real API calls or mock via `--dry-run` |
| Idea generation + money filter | ✅ | Groq / Cerebras / Anthropic with auto-fallback |
| AKF schema validation | ✅ | E001–E008 error codes, max 2 retries per field |
| Lead metadata on every idea | ✅ | `source_url`, `source_company`, `source_author` in frontmatter |
| REST API (Railway) | ✅ | `POST /run`, `GET /runs`, `GET /runs/{id}/logs` |
| Match engine | 🔲 | Pipeline 3 — in spec |
| Offer generator | 🔲 | Pipeline 3 — in spec |
| Send + track | 🔲 | Pipeline 3 — in spec |

---

## Stack

| Layer | Technology |
|---|---|
| Signal mining | Python, httpx, praw (Reddit), HN Algolia API |
| LLM routing | Groq (llama-3.3-70b), Cerebras (llama3.3-70b), Anthropic Claude (fallback) |
| Validation | Custom schema validator (E001–E008), YAML frontmatter |
| API | FastAPI, uvicorn, Railway |
| Execution | gspread (Sheets), imapclient (email) |
| Config | pydantic-settings, python-dotenv |

LLM provider priority: Groq → Cerebras → Anthropic. The router tracks TPM/TPD limits and fails over automatically on 429s.

---

## API

Deployed at `https://web-production-61489.up.railway.app`. Auth via `X-API-Key` header.

### Start a pipeline run

```bash
POST /run?dry_run=true
X-API-Key: <key>
```

Response:
```json
{
  "message": "Pipeline started",
  "run_id": "run_20260404_220006",
  "pid": 3,
  "dry_run": true
}
```

### Get run status and validated ideas

```bash
GET /runs/{run_id}
X-API-Key: <key>
```

Returns `status.json` fields + `report.json` + full content of all `validated/*.md` files.

### Stream logs

```bash
GET /runs/{run_id}/logs
X-API-Key: <key>
```

Returns raw `logs.txt`. Each line:
```
[2026-04-04T22:00:22Z] [run_20260404_220006] [VALIDATION] [SUCCESS] validated/ populated
```

### List all runs

```bash
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

Results in `workspace/runs/<RUN_ID>/`.

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

`source_url` links directly to the person and post that created the signal.

---

## Roadmap — Pipeline 3

**Match → Offer → Send**

```
workspace/matches/matches.json
  idea.domain ↔ lead.pain keywords
  idea.target_user ↔ lead.company profile
  fit_score per pair

workspace/offers/offer_N.md
  references the exact HN post the company wrote
  shows the relevant validated solution
  includes deployed demo URL if available

Agent-Guidelines/email-send
  sends offer
  logs to Google Sheets: sent / opened / replied / closed
  follow-up schedule: day 3, day 7, day 14
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
│   ├── client_finder.py                   ← standalone lead scanner
│   ├── leads/leads.json
│   └── runs/<RUN_ID>/
│       ├── ideas.json
│       ├── connector.json
│       ├── validated/idea_N.md
│       ├── logs.txt
│       ├── status.json
│       └── report.json
├── ai-knowledge-filler/akf.py             ← schema validation + lead metadata injection
├── Agent-Guidelines-for-Upwork-Learning-Projects/  ← Sheets + email execution
└── requirements.txt
```
