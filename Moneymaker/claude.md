# Moneymaker — Claude/Anthropic Integration

## 🤖 AI Provider

This project uses **Anthropic Claude** as its AI backbone for all generative and evaluative tasks.

### Model

| Setting | Default | Env Var |
|---------|---------|---------|
| Model | `claude-3-5-haiku-20241022` | `ANTHROPIC_MODEL` |
| API Key | — | `ANTHROPIC_API_KEY` |

---

## 🧠 Core Philosophy

> **"The agent does not build products. It builds money tests."**

### Hard Constraints

**NEVER:**
- Build microservices
- Design scalable architecture upfront
- Spend >24h on MVP before validation
- Optimize before the first user

### Success Metrics

**NOT:**
- Code quality
- Architecture
- Idea novelty

**ONLY:**
- First payment
- Repeat users
- Conversion rate
- Speed to validation

---

## 🔥 Autonomous System Behavior

The agent is allowed to:
- Discard ideas automatically
- Launch MVP without approval
- Post publicly
- Simulate manual backend
- Iterate based on engagement

---

## 🗺 Where Claude Is Used

| Layer | File | Purpose |
|-------|------|---------|
| Layer 2 — Idea Generator | `src/idea_generator.py` | Converts pain signals into product ideas |
| Layer 3 — Money Filter | `src/money_filter.py` | Scores and filters ideas by monetization criteria |
| Layer 4 — MVP Builder | `src/mvp_builder.py` | Generates actionable MVP plans |

### Fallback Behavior

All Claude-powered layers fall back to **rule-based heuristics** when:
- `ANTHROPIC_API_KEY` is not set
- `--dry-run` flag is passed
- The API call fails after 3 retry attempts

---

## 🔧 Setup

```bash
cp .env.example .env
# Set ANTHROPIC_API_KEY in .env
pip install -r requirements.txt
```

### Dry-run (no API calls)

```bash
python main.py --dry-run
```

### Live run with Claude

```bash
python main.py --sources reddit producthunt --limit 20
```

---

## 📦 Dependency

```
anthropic>=0.30.0
```

Async client: `anthropic.AsyncAnthropic`
Error base class for retry: `anthropic.APIError`
