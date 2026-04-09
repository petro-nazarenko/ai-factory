# AI Factory — Система прогресса

> Обновлено: 2026-04-09  
> Версия: 0.3.0

Этот файл — единая точка отслеживания статуса всех задач по проекту.  
Обновляй после каждого значимого изменения.

---

## Легенда

```
- [x]  выполнено
- [~]  в процессе
- [ ]  не начато
- [!]  заблокировано / требует решения
```

---

## PIPELINE 1 — Signal → Idea → Validate

### Ядро

- [x] Signal mining — HN Algolia API
- [x] Signal mining — RemoteOK RSS
- [x] Signal mining — Reddit (praw)
- [x] `--dry-run` режим (mock данные)
- [x] LLM routing: Groq → Cerebras → Anthropic
- [x] Money Filter (score ≥ 7.0, 4 критерия)
- [x] AKF validation (E001–E008)
- [x] Retry логика (max 2 per field)
- [x] Lead metadata в frontmatter (`source_url`, `source_company`, `source_author`)
- [x] `status.json` обновляется на каждом шаге
- [x] `report.json` после завершения run
- [x] `logs.txt` — append-only, формат `[TS][RUN_ID][STEP][STATUS]`

### Стабилизация (v0.2.0 → v0.3.0)

- [x] HTTP timeout для jobboards.py — semaphore cap (20 concurrent)
- [ ] Pydantic-валидация входных данных в connector.py
- [ ] Логирование причины LLM fallback в logs.txt
- [x] Integrity check output-файлов в run_pipeline.sh (guards added)
- [x] `.gitignore` покрывает `workspace/runs/`, `workspace/leads/`, `workspace/matches/`, `workspace/offers/`

---

## PIPELINE 2 — REST API

- [x] `POST /run` — запуск pipeline
- [x] `POST /run?dry_run=true` — сухой запуск
- [x] `GET /runs` — список всех run
- [x] `GET /runs/{run_id}` — статус + validated ideas
- [x] `GET /runs/{run_id}/logs` — raw logs
- [x] Деплой на Railway (auto-deploy от main)
- [x] Auth через `X-API-Key` header
- [ ] Rate limiting на `POST /run` (max 3 параллельных)
- [ ] Ограничение размера ответа `GET /runs/{id}` (pagination или truncation)
- [ ] Поддержка нескольких API-ключей

---

## PIPELINE 3 — Match → Offer → Send

### Matching Engine

- [x] `workspace/matcher.py` — keyword + LLM fit scoring
- [x] Keyword overlap: `idea.tags` ↔ `lead.pain` (Jaccard, 0–5 scale)
- [x] LLM fit score (0–10) via llm_router
- [x] Output: `workspace/matches/matches.json`
- [x] Unit-тесты (`workspace/tests/test_matcher.py`)

### Offer Generator

- [x] `workspace/offer_generator.py` — primary flow from connector.json
- [x] Шаблон персонализированного сообщения (LLM-generated)
- [x] Ссылка на конкретный пост источника
- [x] CTA (звонок / пилот)
- [x] Output: `workspace/offers/offer_N.md`
- [x] Unit-тесты (`workspace/tests/test_offer_generator.py`)

### Action Layer

- [ ] Интеграция с `Agent-Guidelines/email-send`
- [ ] Google Sheets tracking (sent / opened / replied / closed)
- [ ] Follow-up: day 3, day 7, day 14
- [ ] REST endpoint `POST /match-and-send`
- [ ] E2E тест (dry-run)

---

## CLIENT FINDER

- [x] `workspace/client_finder.py` — базовая версия
- [ ] Интеграция в основной pipeline
- [ ] Дедупликация по `source_url`
- [ ] Обогащение данными (company size, stack)
- [ ] Поддержка Upwork RSS как источника

---

## SALESAI MODULE

- [x] `SalesAI/README.md` — описание модуля
- [ ] `SalesAI/` — выделить в самостоятельный сервис
- [ ] REST API: `POST /assess`
- [ ] Интеграция с Pipeline 3
- [ ] Demo deployment

---

## ТЕСТИРОВАНИЕ

- [x] Unit-тесты: `workspace/connector.py` (`workspace/tests/test_connector.py`)
- [x] Unit-тесты: `workspace/matcher.py` (`workspace/tests/test_matcher.py`)
- [x] Unit-тесты: `workspace/offer_generator.py` (`workspace/tests/test_offer_generator.py`)
- [x] Unit-тесты: `workspace/client_finder.py` (`workspace/tests/test_client_finder.py`)
- [ ] Unit-тесты: AKF retry-логика
- [ ] E2E тест: `bash run_pipeline.sh --dry-run` в CI
- [ ] CI coverage report

---

## OBSERVABILITY

- [ ] Correlation ID / request tracing (`structlog.contextvars`)
- [ ] Метрики: `api_calls_total`, `api_errors_total`, `retry_count`
- [ ] Health-check endpoint `GET /health`
- [ ] Sentry (или аналог) для production

---

## БЕЗОПАСНОСТЬ

- [!] Проверить `.gitignore` на покрытие `**/.env` — КРИТИЧНО
- [ ] `pydantic.SecretStr` для паролей и ключей
- [ ] `pip audit` в CI
- [ ] Поддержка `GOOGLE_SHEETS_CREDENTIALS_JSON` (base64 env var)
- [ ] Multi-key API auth с ротацией

---

## ДОКУМЕНТАЦИЯ

- [x] `README.md` — обзор проекта
- [x] `SHORTCUTS.md` — cheatsheet команд
- [x] `CLAUDE.md` — operator spec для AI
- [x] `AUDIT.md` — аудит рисков ← создан
- [x] `ROADMAP.md` — дорожная карта ← создан
- [x] `WHITEPAPER.md` — технический whitepaper ← создан
- [x] `PROGRESS.md` — этот файл ← создан
- [ ] `docs/DEPLOY.md` — runbook для деплоя
- [ ] `docs/ARCHITECTURE.md` — детальная схема компонентов

---

## РЕЛИЗЫ

| Версия | Статус | Содержание |
|---|---|---|
| v0.1.0 | ✅ shipped | Pipeline 1 + REST API |
| v0.2.0 | ✅ shipped | Стабилизация + документация |
| v0.3.0 | 🔄 текущий | Pipeline 3 MVP (matcher + offer_generator + tests) |
| v0.4.0 | [ ] planned | Observability + Client Finder |
| v0.5.0 | [ ] planned | SalesAI + hardening |
| v1.0.0 | [ ] planned | Production release |

---

## История обновлений

| Дата | Изменение |
|---|---|
| 2026-04-09 | workspace/matcher.py, offer_generator.py, run_utils.py, tests/; CI workflow; security fixes |
| 2026-04-05 | Созданы AUDIT.md, ROADMAP.md, WHITEPAPER.md, PROGRESS.md |
| 2026-04-04 | REST API задеплоен на Railway |
| 2026-04-04 | Lead metadata добавлен в frontmatter |
| 2026-04-01 | Pipeline 1 end-to-end работает |
