# API Reference

Base URL: `https://web-production-61489.up.railway.app`

All endpoints require `X-API-Key: <key>` header.

---

## POST /run

Start a pipeline run.

**Query params**

| Param | Type | Default | Description |
|---|---|---|---|
| `dry_run` | bool | `false` | Use mock data; no external LLM or API calls |

**Response**

```json
{
  "message": "Pipeline started",
  "run_id": "run_20260404_220006",
  "pid": 3,
  "dry_run": true
}
```

---

## GET /runs

List all runs.

**Response** — array of run summary objects, newest first.

```json
[
  {
    "run_id": "run_20260404_220006",
    "status": "success",
    "created": "2026-04-04T22:00:06Z"
  }
]
```

---

## GET /runs/{run_id}

Get full run details: status, report, and all validated idea files.

**Response**

```json
{
  "run_id": "run_20260404_220006",
  "status": "success",
  "report": { ... },
  "validated": [
    {
      "file": "idea_1.md",
      "content": "---\ntitle: ...\n---\n## Problem\n..."
    }
  ]
}
```

---

## GET /runs/{run_id}/logs

Stream raw log output for a run.

**Response** — plain text, one log line per line.

```
[2026-04-04T22:00:22Z] [run_20260404_220006] [INIT] [SUCCESS] run created
[2026-04-04T22:00:24Z] [run_20260404_220006] [IDEA_GEN] [RUNNING] 20 signals found
[2026-04-04T22:00:38Z] [run_20260404_220006] [VALIDATION] [SUCCESS] validated/ populated
```

---

## Error responses

| Code | Meaning |
|---|---|
| `401` | Missing or invalid `X-API-Key` |
| `404` | Run ID not found |
| `500` | Pipeline error — check `/runs/{run_id}/logs` |
