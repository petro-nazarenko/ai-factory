# Moneymaker — MVP Idea Engine v2

> 🤖 **Fully Autonomous System** — automatically finds, filters, and validates startup ideas
> all the way to the *first paying user → $1k MRR trajectory*.

---

## 🧠 System Overview (4 Layers)

| # | Layer | What it does |
|---|-------|-------------|
| 1 | **Signal Miner** | Scrapes Reddit, Product Hunt, IndieHackers, and job boards for pain signals |
| 2 | **Idea Generator** | Converts each signal into 1–3 concrete product ideas via Claude (Anthropic) |
| 3 | **Money Filter Engine** | Hard-filters ideas: existing spend behaviour, clear buyer, MVP ≤ 24 h |
| 4 | **Autonomous MVP Builder** | Outputs a ready-to-execute MVP plan with template code/copy |

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in your API keys (OPENAI_API_KEY is required for AI-powered mode)
```

### 3. Run the pipeline

```bash
# Dry-run (no external API calls – uses mock data)
python main.py --dry-run

# Live run with all sources
python main.py --sources reddit producthunt indiehackers jobboards --limit 20

# Save JSON report to file
python main.py --dry-run --output report.json
```

---

## 🗂 Project Structure

```
.
├── main.py                   # CLI entry point
├── src/
│   ├── config.py             # Settings from environment variables
│   ├── models.py             # Pydantic data models
│   ├── engine.py             # Main pipeline orchestrator
│   ├── idea_generator.py     # Layer 2: pain → ideas (OpenAI)
│   ├── money_filter.py       # Layer 3: idea scoring & rejection
│   ├── mvp_builder.py        # Layer 4: MVP plan + template generation
│   └── signal_miner/
│       ├── base.py           # Abstract base miner
│       ├── reddit.py         # Reddit miner (PRAW)
│       ├── producthunt.py    # Product Hunt GraphQL miner
│       ├── indiehackers.py   # IndieHackers HTML scraper
│       └── jobboards.py      # Upwork RSS miner
└── tests/
    ├── test_models.py
    ├── test_signal_miners.py
    ├── test_idea_generator.py
    ├── test_money_filter.py
    └── test_engine.py
```

---

## 💡 Money Filter Criteria

An idea **passes** only if:

- ✅ **Existing spending behavior** — target user already pays for adjacent tools
- ✅ **Clear buyer** — identifiable person who would buy on day 1
- ✅ **MVP feasible in ≤ 24 h** — first version buildable solo in a day
- ✅ **Sellable without brand** — can close first sale with zero audience

**Auto-rejected** if any of:

- ❌ `future_market` — framing relies on a market that doesn't exist yet
- ❌ `no_budget_users` — target users have no tool budget
- ❌ `social_only_value` — value only exists at scale (chicken-egg day 1)

---

## 🔨 MVP Formats

| Format | When chosen | Build time |
|--------|-------------|-----------|
| `landing_page` | Default | 2–4 h |
| `telegram_bot` | Solution mentions bot/Telegram | 3–6 h |
| `google_form_manual` | Concierge / done-for-you service | 1–2 h |
| `api_wrapper` | Solution is an API/integration | 4–8 h |

---

## 🧪 Running Tests

```bash
pytest
```

---

## ⚙️ Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes (live mode) | Anthropic API key for idea generation & scoring via Claude |
| `ANTHROPIC_MODEL` | No | Claude model name (default: `claude-3-5-haiku-20241022`) |
| `REDDIT_CLIENT_ID` | No | Reddit API client ID |
| `REDDIT_CLIENT_SECRET` | No | Reddit API client secret |
| `PRODUCTHUNT_TOKEN` | No | Product Hunt OAuth token |
| `SIGNAL_MIN_SCORE` | No | Minimum signal score 0–10 (default: `6`) |
| `IDEAS_PER_SIGNAL` | No | Ideas generated per signal (default: `3`) |

> All external API integrations are **optional**. The system falls back to
> mock data when credentials are absent or `--dry-run` is passed.
