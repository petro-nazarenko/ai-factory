# AI Factory — Система прогресса

> Обновлено: 2026-04-05  
> Версия: 0.2.0

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

### Стабилизация (v0.2.0)

- [ ] HTTP timeout для jobboards.py (10 сек)
- [ ] Pydantic-валидация входных данных в connector.py
- [ ] Логирование причины LLM fallback в logs.txt
- [ ] Integrity check output-файлов в run_pipeline.sh
- [!] `.gitignore` покрывает все `**/.env` паттерны — **проверить немедленно**

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

- [ ] `workspace/matcher.py` — базовая реализация
- [ ] Keyword overlap: `idea.tags` ↔ `lead.pain`
- [ ] Domain match: `idea.domain` == `lead.domain`
- [ ] LLM fit score (0–10)
- [ ] Output: `workspace/matches/matches.json`
- [ ] Unit-тесты

### Offer Generator

- [ ] `workspace/offer_generator.py`
- [ ] Шаблон персонализированного сообщения
- [ ] Ссылка на конкретный пост источника
- [ ] CTA (звонок / пилот)
- [ ] Output: `workspace/offers/offer_N.md`
- [ ] Unit-тесты

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

- [ ] Unit-тесты: `workspace/connector.py`
- [ ] Unit-тесты: `workspace/llm_router.py`
- [ ] Unit-тесты: `workspace/client_finder.py`
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
| v0.2.0 | 🔄 текущий | Стабилизация + документация |
| v0.3.0 | [ ] planned | Pipeline 3 MVP |
| v0.4.0 | [ ] planned | Observability + Client Finder |
| v0.5.0 | [ ] planned | SalesAI + hardening |
| v1.0.0 | [ ] planned | Production release |

---

## История обновлений

| Дата | Изменение |
|---|---|
| 2026-04-05 | Созданы AUDIT.md, ROADMAP.md, WHITEPAPER.md, PROGRESS.md |
| 2026-04-04 | REST API задеплоен на Railway |
| 2026-04-04 | Lead metadata добавлен в frontmatter |
| 2026-04-01 | Pipeline 1 end-to-end работает |
