# AI Factory — Roadmap

> Версия: 0.3.0  
> Обновлено: 2026-04-09  
> Стратегия: signal → idea → lead → offer → closed deal

---

## Текущий статус

| Pipeline | Статус |
|---|---|
| Pipeline 1 — Signal → Idea → Validate | ✅ Работает |
| Pipeline 2 — REST API + Railway deploy | ✅ Работает |
| Pipeline 3 — Match → Offer → Send | 🔄 Частично (match + offer готовы, send — TODO) |

---

## ФАЗА 1 — Стабилизация ядра (Pipeline 1)

**Цель:** Pipeline 1 работает без сбоев на реальных данных.

- [x] Signal mining — HN + RemoteOK
- [x] LLM routing — Groq → Cerebras → Anthropic fallback
- [x] Money Filter (score ≥ 7.0)
- [x] AKF validation (E001–E008, max 2 retry)
- [x] Lead metadata в frontmatter (`source_url`, `source_company`, `source_author`)
- [x] REST API: `POST /run`, `GET /runs`, `GET /runs/{id}/logs`
- [ ] HTTP timeout для всех внешних запросов (jobboards.py)
- [ ] Pydantic-валидация входных данных в connector.py
- [ ] Rate limiting на `POST /run` (max 3 параллельных запуска)
- [ ] Dry-run тест в CI (end-to-end `--dry-run`)
- [x] Unit-тесты для `workspace/` модулей (connector, matcher, offer_generator, client_finder)
- [x] CI workflow (lint + tests) на GitHub Actions

**Оценка:** ~8 ч

---

## ФАЗА 2 — Pipeline 3: Match → Offer → Send

**Цель:** от validated идеи до отправленного оффера без ручного участия.

### 2.1 Matching Engine ✅

- [x] `workspace/matcher.py` — keyword + LLM fit scoring
- [x] Fit score: keyword Jaccard (0–5) + LLM scorer (0–10)
- [x] Output: `workspace/matches/matches.json`
- [x] Unit-тесты (`workspace/tests/test_matcher.py`)

### 2.2 Offer Generator ✅

- [x] `workspace/offer_generator.py` — персонализированное сообщение per lead
- [x] Primary flow: connector.json → offer per idea author
- [x] Legacy flow: matches.json (--from-matches flag)
- [x] Поддержка deployed demo URL (если есть)
- [x] Output: `workspace/offers/offer_N.md`
- [x] Unit-тесты (`workspace/tests/test_offer_generator.py`)

### 2.3 Action Layer

- [ ] Интеграция с `Agent-Guidelines/email-send`
- [ ] Google Sheets tracking: `sent | opened | replied | closed`
- [ ] Follow-up расписание: day 3, day 7, day 14
- [ ] REST endpoint `POST /match-and-send`

**Оценка:** 8 ч

---

## ФАЗА 3 — Observability

**Цель:** видеть состояние системы в реальном времени.

- [ ] Correlation ID / request tracing через `structlog.contextvars`
- [ ] Метрики: `api_calls_total`, `api_errors_total`, `retry_count`
- [ ] Health-check endpoint `GET /health` с проверкой LLM connectivity
- [ ] Fallback-логирование: причина переключения провайдера в `logs.txt`
- [ ] Sentry или аналог для capture exceptions в production

**Оценка:** ~15 ч

---

## ФАЗА 4 — Leads Discovery (Client Finder)

**Цель:** автоматический поиск лидов без участия пользователя.

- [x] `workspace/client_finder.py` — реализован с semaphore (20 concurrent HN requests)
- [ ] Полная интеграция в основной pipeline
- [ ] Источники: HN "Who is hiring", LinkedIn Jobs (через API/scrape), Upwork RSS
- [ ] Дедупликация лидов (по `source_url`)
- [ ] Обогащение: company size, tech stack из публичных профилей
- [ ] Output: `workspace/leads/leads.json`

**Оценка:** 12 ч

---

## ФАЗА 5 — SalesAI Module

**Цель:** специализированный модуль под SDR-автоматизацию.

- [ ] `SalesAI/` — выделить в самостоятельный deployable сервис
- [ ] REST API: `POST /assess` — оценка SDR-кандидата по заданным критериям
- [ ] Интеграция с Pipeline 3 как offer template
- [ ] Demo deployment (Railway или Render)
- [ ] README с примером использования

**Оценка:** 12 ч

---

## ФАЗА 6 — Product Hardening

**Цель:** готовность к публичному релизу v1.0.

- [ ] `uv.lock` / `requirements.lock` — lock-файл зависимостей
- [ ] `pip audit` в CI
- [ ] `pydantic.SecretStr` для всех паролей и ключей
- [ ] Multi-key API auth с ротацией
- [ ] Runbook для деплоя в `docs/DEPLOY.md`
- [ ] Makefile с целями: `lint`, `test`, `dry-run`, `deploy`
- [ ] Тег `v1.0.0` + GitHub Release

**Оценка:** ~15 ч

---

## Общая оценка

| Фаза | Оценка | Приоритет |
|---|---|---|
| 1 — Стабилизация | ~8 ч | 🔴 СЕЙЧАС |
| 2 — Pipeline 3 | ~22 ч | 🔴 СЕЙЧАС |
| 3 — Observability | ~15 ч | 🟡 NEXT |
| 4 — Leads Discovery | ~12 ч | 🟡 NEXT |
| 5 — SalesAI Module | ~12 ч | 🟢 LATER |
| 6 — Hardening | ~15 ч | 🟢 BEFORE v1.0 |

**Итого: ~84 ч** до v1.0.

---

## Версионирование

| Версия | Содержание |
|---|---|
| `v0.1.0` | Pipeline 1 + REST API (shipped) |
| `v0.2.0` | Стабилизация + dry-run тесты (shipped) |
| `v0.3.0` | Pipeline 3 MVP (Match + Offer) + workspace tests + CI (текущий) |
| `v0.4.0` | Send + Track + Observability + Client Finder integration |
| `v0.5.0` | SalesAI + hardening |
| `v1.0.0` | Production release |
