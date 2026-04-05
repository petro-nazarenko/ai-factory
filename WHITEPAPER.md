# AI Factory — Whitepaper

> Версия: 0.2.0  
> Дата: 2026-04-05  
> Авторы: AI Factory Team

---

## Abstract

AI Factory — это автономная система для превращения рыночных сигналов в закрытые сделки. Система непрерывно сканирует источники найма и жалоб (HN, RemoteOK, Reddit), извлекает боль, конвертирует её в validated продуктовые идеи, находит компанию-источник сигнала и генерирует персонализированное предложение — всё без ручного участия.

Ключевое отличие от традиционных инструментов генерации идей: каждая идея несёт в себе готовый лид — компанию, которая уже тратит деньги на эту проблему.

---

## 1. Проблема

Фрилансеры, инди-разработчики и стартапы тратят значительную часть времени на поиск клиентов вручную. Типичный цикл:

1. Просмотр job boards → поиск релевантных постов (2–4 часа/день)
2. Оценка потенциала задачи (субъективно, без данных)
3. Написание предложения под каждую заявку (30–60 минут/предложение)
4. Отслеживание ответов в таблице или в голове

Конверсия холодных предложений — 2–5%. Из 100 отправленных — 2–5 ответов.

**AI Factory решает это через автоматизацию шагов 1–3 и повышение релевантности предложений.**

---

## 2. Решение

### 2.1 Архитектура

```
Источники сигналов
  HN "Who is hiring" ──┐
  RemoteOK             ├──► [Signal Miner] ──► [Money Filter] ──► [AKF Validator]
  Reddit r/SaaS        ┘         │                                      │
                                 ▼                                      ▼
                           PainSignal                           validated/idea_N.md
                         (score, source)                     (YAML frontmatter + spec)
                                                                        │
                                                                        ▼
                                                              [Matcher] ──► matches.json
                                                                        │
                                                                        ▼
                                                            [Offer Generator] ──► offer_N.md
                                                                        │
                                                                        ▼
                                                                 [Action Layer]
                                                               email / Sheets / DM
```

### 2.2 Ключевые компоненты

**Signal Miner (Moneymaker)**  
Извлекает сигналы боли из HN, RemoteOK, Reddit. Каждый сигнал включает: текст боли, источник (URL, компания, автор), дату, платформу.

**Money Filter**  
LLM-оценка по 4 критериям:
- Есть ли существующее spend-поведение? (покупают ли это сейчас)
- Есть ли конкретный buyer?
- Можно ли сделать MVP за 24 часа?
- Продаётся ли без бренда?

Только идеи с score ≥ 7.0 проходят дальше.

**AKF Validator (ai-knowledge-filler)**  
Структурирует идею по схеме. 8 типов ошибок (E001–E008), max 2 retry на поле. Output: Markdown-файл с YAML frontmatter + разделы Problem / Solution / Revenue / MVP.

**LLM Router**  
Единая точка входа для всех LLM-вызовов. Приоритет: Groq → Cerebras → Anthropic. Автоматический failover при 429 (rate limit).

**REST API (ai-factory-api)**  
FastAPI-сервис на Railway. Endpoints: `POST /run`, `GET /runs`, `GET /runs/{id}/logs`.

---

## 3. Модель данных

### PainSignal (Moneymaker output)

```python
class PainSignal:
    signal: str           # текст боли
    score: float          # 0.0–10.0
    source_url: str       # прямая ссылка на пост
    source_company: str   # название компании
    source_author: str    # username автора
    source_platform: str  # "jobboards" | "reddit"
    posted_date: str      # ISO 8601
```

### Validated Idea (AKF output)

```yaml
---
title: "SDR Assessment Automation Tool"
type: guide
domain: automation
level: intermediate
status: active
tags: [sales, automation, ai, assessment]
created: "2026-04-05T00:00:00Z"
updated: "2026-04-05T00:00:00Z"
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

### Run Report (pipeline output)

```json
{
  "run_id": "run_20260405_120000",
  "mode": "GENERATE_ONLY",
  "status": "success",
  "ideas_mined": 20,
  "ideas_passed_filter": 5,
  "ideas_validated": 4,
  "ideas_failed": 1,
  "duration_seconds": 38
}
```

---

## 4. LLM Strategy

### Провайдеры

| Провайдер | Модель | Приоритет | Лимит (TPM) |
|---|---|---|---|
| Groq | llama-3.3-70b | 1 (primary) | 6,000 TPM |
| Cerebras | llama3.3-70b | 2 (secondary) | 8,000 TPM |
| Anthropic | Claude Haiku | 3 (fallback) | no limit |

### Fallover логика

```
Запрос → Groq
  └─ 429 / timeout → Cerebras
       └─ 429 / timeout → Anthropic Claude
            └─ failure → ABORT, log error
```

Провайдер выбирается автоматически на основе текущего использования TPM/TPD. Router отслеживает расход токенов per provider per minute/day.

---

## 5. Pipeline 3 — Match → Offer → Send (roadmap)

**Текущее состояние:** spec готов, реализация — в разработке.

### Matching Engine

Входные данные:
- `validated/*.md` — структурированные идеи с полем `domain`
- `workspace/leads/leads.json` — лиды с `pain`, `company`, `stack`

Алгоритм:
1. Keyword overlap: `idea.tags` ↔ `lead.pain` words
2. Domain match: `idea.domain` == `lead.domain`
3. LLM fit score (0–10): "насколько это решение решает именно их боль?"

Output: `workspace/matches/matches.json`

### Offer Generator

Для каждого match генерируется персонализированное предложение:
- Ссылка на конкретный пост компании
- Формулировка боли их словами
- Решение из validated идеи
- Ссылка на demo (если задеплоено)
- CTA: предложение звонка или бесплатного пилота

### Action Layer

- Email через `Agent-Guidelines/email-send`
- Google Sheets: `sent | opened | replied | closed`
- Follow-up: day 3, day 7, day 14

---

## 6. Деплой

### Схема деплоя

```
GitHub repo ──► Railway (auto-deploy on push to main)
                    │
                    ├── ai-factory-api/main.py   (FastAPI, PORT=$PORT)
                    └── workspace/               (run artifacts)
```

### Переменные окружения

| Переменная | Обязательна | Описание |
|---|---|---|
| `GROQ_API_KEY` | да (или Cerebras/Anthropic) | Primary LLM |
| `CEREBRAS_API_KEY` | нет | Secondary LLM |
| `ANTHROPIC_API_KEY` | нет | Fallback LLM |
| `API_KEY` | да | REST API auth |
| `SPREADSHEET_ID` | только для FULL_PIPELINE | Google Sheets target |
| `TARGET_EMAIL` | только для FULL_PIPELINE | Outreach email |

---

## 7. Безопасность

- API-ключ в заголовке `X-API-Key` (не в URL)
- `.env`-файлы в `.gitignore`
- LLM API-ключи никогда не попадают в `logs.txt`
- Validated ideas не содержат персональных данных (только публичные посты)
- Railway env vars — зашифрованы at rest

**Планируется:**
- `pydantic.SecretStr` для всех секретов в конфиге
- Multi-key API auth
- `pip audit` в CI

---

## 8. Метрики успеха

| Метрика | Текущее | Цель (v1.0) |
|---|---|---|
| Сигналов за run | 20 | 50+ |
| Идей после Money Filter (%) | ~25% | >30% |
| Валидированных идей (%) | ~80% | >90% |
| Время полного run | ~40 сек | <60 сек |
| Конверсия оффер → ответ | n/a | >10% |
| Uptime API | ~99% | >99.5% |

---

## 9. Конкурентный анализ

| Инструмент | Что делает | Чего не делает |
|---|---|---|
| Perplexity / ChatGPT | Генерирует идеи | Не находит реальных лидов |
| Apollo / Hunter | Находит контакты | Не генерирует персонализированные офферы |
| Upwork search | Показывает заявки | Не фильтрует по spend-потенциалу |
| AI Factory | Всё вышесказанное end-to-end | Pipeline 3 в разработке |

**Ключевое конкурентное преимущество:** каждая идея содержит конкретный лид — компанию, которая уже написала о своей боли публично.

---

## 10. Лицензия и использование

Проект разработан для internal use и Upwork-фриланса.  
Публичный релиз запланирован после реализации Pipeline 3.
