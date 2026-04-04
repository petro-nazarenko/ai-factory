# ROADMAP — Production Readiness

> Дата аудита: 2026-03-26
> Версия проекта: 0.1.0
> Статус: Alpha — **не готов к production**

---

## ФАЗА 1 — Стабильность (must have)

Проблемы, которые сломают проект в production прямо сейчас.

### 1.1 `delete_email` хардкодит Gmail-путь к корзине

| | |
|---|---|
| **Файл** | `src/integrations/email_handler.py:379` |
| **Проблема** | `self._imap.move(uid, "[Gmail]/Trash")` — работает только с Gmail. На Outlook, Yahoo, корпоративном IMAP упадёт с ошибкой. |
| **Риск** | HIGH |
| **Оценка** | 2 ч |

**Решение:** определять trash-папку динамически через `get_folders()` или принимать её как параметр конфига.

---

### 1.2 CI не запускается на feature-ветках

| | |
|---|---|
| **Файл** | `.github/workflows/ci.yml:3-6` |
| **Проблема** | `on: push: branches: [main, master]` — CI не срабатывает при push в feature-ветки. Ошибки обнаруживаются только при merge в main. |
| **Риск** | HIGH |
| **Оценка** | 1 ч |

**Решение:** убрать фильтр `branches` из `push`, оставить только для PR.

---

### 1.3 `assert` вместо явной проверки соединения

| | |
|---|---|
| **Файл** | `src/integrations/email_handler.py:287, 337, 375, 445` |
| **Проблема** | `assert self._imap is not None` — при запуске Python с флагом `-O` (optimized) все assert-ы отключаются. Вместо понятной ошибки получаем `AttributeError: 'NoneType' object has no attribute 'select_folder'`. |
| **Риск** | HIGH |
| **Оценка** | 1 ч |

**Решение:** заменить `assert` на `if not self._imap: raise IntegrationConnectionError(...)`.

---

### 1.4 `GoogleSheetsSettings.credentials_path` — относительный путь

| | |
|---|---|
| **Файл** | `src/utils/config.py:19-22` |
| **Проблема** | `default=Path("config/credentials.json")` — относительный путь, зависит от CWD. Если сервис запущен не из корня проекта (systemd, Docker), credentials не найдутся. `GoogleSheetsConfig` в `google_sheets.py` использует `~/.config/...` — два разных дефолта для одного параметра. |
| **Риск** | HIGH |
| **Оценка** | 2 ч |

**Решение:** унифицировать дефолт в обоих местах, использовать абсолютный путь через `Path.home()`.

---

### 1.5 `_load_credentials` логирует warning, но всё равно падает

| | |
|---|---|
| **Файл** | `src/integrations/google_sheets.py:110-119` |
| **Проблема** | При отсутствии файла credentials выводит `"continuing in test/mock mode"`, затем немедленно вызывает `Credentials.from_service_account_file()` и падает с `FileNotFoundError`. Вводит в заблуждение. |
| **Риск** | MED |
| **Оценка** | 1 ч |

**Решение:** убрать misleading warning или добавить реальный mock-режим.

---

### 1.6 `open_spreadsheet` поглощает все исключения в `SpreadsheetNotFound`

| | |
|---|---|
| **Файл** | `src/integrations/google_sheets.py:152-155` |
| **Проблема** | `except Exception as e: raise SpreadsheetNotFound(...)` — сетевые ошибки, ошибки авторизации, rate limit — всё становится `SpreadsheetNotFound`. Теряется реальная причина. |
| **Риск** | MED |
| **Оценка** | 2 ч |

**Решение:** разделить обработку: `gspread.exceptions.APIError` → `IntegrationError`, `FileNotFoundError` → `AuthenticationError`, конкретно `SpreadsheetNotFound` — только когда лист не найден.

---

### 1.7 `configure_logging()` вызывается при каждом `get_logger()`

| | |
|---|---|
| **Файл** | `src/utils/logger.py:25` |
| **Проблема** | `get_logger()` вызывает `configure_logging()` каждый раз. Structlog переконфигурируется при каждом обращении к логгеру — это не thread-safe и создаёт лишние накладные расходы. |
| **Риск** | MED |
| **Оценка** | 1 ч |

**Решение:** вызывать `configure_logging()` один раз при старте приложения (в `cli.py` или `__init__`), убрать вызов из `get_logger()`.

---

### 1.8 Уровень логирования не читается из конфига

| | |
|---|---|
| **Файл** | `src/utils/logger.py:9`, `src/utils/config.py:82` |
| **Проблема** | `DEFAULT_LOG_LEVEL = logging.INFO` — хардкод. `AppSettings.log_level` существует в конфиге, но `get_logger()` его не использует. В production нельзя изменить уровень через `LOG_LEVEL=DEBUG`. |
| **Риск** | MED |
| **Оценка** | 2 ч |

**Решение:** в точке входа CLI читать `load_config().app.log_level` и передавать в `configure_logging()`.

---

### 1.9 `with_retry` по умолчанию ловит все `Exception`

| | |
|---|---|
| **Файл** | `src/utils/retry.py:23` |
| **Проблема** | `exceptions: tuple[type[Exception], ...] = (Exception,)` — повторные попытки при `KeyboardInterrupt`, `SystemExit`, `AuthenticationError`. Авторизационные ошибки не должны ретраиться — это лишь замедляет провал. |
| **Риск** | MED |
| **Оценка** | 2 ч |

**Решение:** исключить `AuthenticationError` из retry по умолчанию, добавить явный список ретраиваемых ошибок (сетевые, rate limit).

---

**Итого Фаза 1: ~14 ч**

---

## ФАЗА 2 — Надёжность (should have)

Проблемы, которые проявятся под нагрузкой или с реальными данными.

### 2.1 SMTP-соединение не переиспользуется

`send_email` проверяет `if not self._smtp: self.connect_smtp()` внутри метода, но соединение может протухнуть между вызовами. Нет heartbeat / SMTP NOOP. При долгой работе сервиса — `SMTPServerDisconnected`.

**Оценка:** 3 ч

### 2.2 `batch_write` не обёрнут в `@with_retry`

`read_range` и `write_range` имеют `@with_retry(max_attempts=3)`, но `batch_write` (`google_sheets.py:301`) — нет. Транзиентные сетевые ошибки при batch-операциях не ретраиваются.

**Оценка:** 1 ч

### 2.3 `fetch_emails` использует `select_folder(readonly=False)` при чтении

`google_sheets.py:290` — открывает папку в режиме записи при каждом fetch. Лишние права, может вызвать проблемы с конкурентным доступом.

**Оценка:** 1 ч

### 2.4 `search_criteria` не защищён от injection

`email_handler.py:296` — `f"SINCE {since_date.strftime('%d-%b-%Y')}"` добавляется напрямую в IMAP search criteria. При нестандартном значении `since_date` возможна некорректная IMAP команда.

**Оценка:** 2 ч

### 2.5 Нет интеграционных тестов

Все тесты — unit с моками. Реальное поведение при подключении к Google Sheets API, SMTP/IMAP серверу, обработке реальных PDF — не проверено. Баги в протоколе взаимодействия обнаруживаются только в production.

**Оценка:** 16 ч (создание test fixtures + базовые интеграционные сценарии)

### 2.6 Нет connection pooling для HTTP

Bol.com API клиент в `examples/bol_com/` создаёт новый `httpx.Client` на каждый запрос. При интенсивном использовании — исчерпание сокетов.

**Оценка:** 3 ч

### 2.7 Покрытие тестами — 75%, критические пути не покрыты

- `base.py`: `retry_with_backoff`, `_handle_rate_limit`, `_validate_config` — 0%
- `google_sheets.py`: `batch_write`, `create_worksheet`, `delete_worksheet` — 0%
- `email_handler.py`: `mark_as_read`, `delete_email`, `get_folders` — 0%

**Оценка:** 8 ч

---

**Итого Фаза 2: ~34 ч**

---

## ФАЗА 3 — Observability (should have)

### 3.1 Нет correlation ID / request tracing

Каждый запрос к внешнему API логируется изолированно. При дебаге цепочки операций невозможно связать логи между собой.

**Решение:** использовать `structlog.contextvars` для передачи `request_id` через весь стек вызовов.
**Оценка:** 4 ч

### 3.2 Нет метрик

Нет счётчиков вызовов API, latency, количества retry, rate limit hits. Невозможно заметить деградацию до того, как она станет outage.

**Решение:** добавить `prometheus-client` или аналог; экспортировать `api_calls_total`, `api_errors_total`, `retry_count`.
**Оценка:** 8 ч

### 3.3 Нет health-check endpoint

Нет способа проверить доступность сервиса из оркестратора (Kubernetes, Docker Compose healthcheck).

**Решение:** добавить `upwork-learn health` команду в CLI, которая проверяет connectivity к Google Sheets и SMTP.
**Оценка:** 3 ч

### 3.4 Алерты не настроены

Нет уведомлений при критических ошибках (AuthenticationError, исчерпание retry). Об инцидентах узнают постфактум.

**Решение:** добавить Sentry или аналог для capture exceptions в production.
**Оценка:** 4 ч

### 3.5 Логи не содержат контекста операции

В большинстве мест логируется только `error=str(e)`. Нет `operation`, `user`, `spreadsheet_id` в контексте ошибки. Дебаг по логам крайне затруднён.

**Оценка:** 3 ч

---

**Итого Фаза 3: ~22 ч**

---

## ФАЗА 4 — Developer Experience (nice to have)

### 4.1 CI не покрывает feature-ветки (повтор из Фазы 1)

Уже описано в п. 1.2. Критично для DX — разработчики не получают обратную связь без PR.

**Оценка:** 1 ч

### 4.2 `uv pip install --all-extras` не устанавливает пакет в editable-режиме

В `ci.yml:30` — `uv pip install --all-extras` устанавливает зависимости, но не сам пакет. Команды `ruff`, `mypy`, `pytest` могут работать иначе, чем после `pip install -e .`.

**Решение:** `uv pip install -e ".[dev,security]"` или `uv sync`.
**Оценка:** 1 ч

### 4.3 `preflight.sh` — mypy в soft-режиме

mypy не блокирует commit (`MYPY_FAILED` не влияет на exit code). Разработчик видит ошибки типов, но может игнорировать. В CI mypy — hard-fail.

**Решение:** сделать mypy hard-fail и в preflight.
**Оценка:** 0.5 ч

### 4.4 Нет Makefile / единой точки входа

Для запуска всех проверок нужно знать: `bash preflight.sh` vs `nox -s all_checks` vs `nox -s lint` vs `ruff check src/`. Новый разработчик не знает что запускать.

**Решение:** добавить `Makefile` с целями `lint`, `test`, `typecheck`, `fmt`, `all`.
**Оценка:** 2 ч

### 4.5 `pytest-asyncio` warning в тестах

`pyproject.toml:122` — `asyncio_mode = "auto"`, но `pytest-asyncio` устанавливается только в dev-окружении через nox. В локальном `pip install -e .[dev]` — OK. В чистом venv без nox — warning о неизвестном ini-option.

**Оценка:** 1 ч

### 4.6 Нет runbook для деплоя

Нет документа с пошаговой инструкцией: как создать service account, где положить credentials.json, как выставить переменные окружения, как проверить что всё работает.

**Оценка:** 4 ч

---

**Итого Фаза 4: ~9.5 ч**

---

## ФАЗА 5 — Security (must have before public)

### 5.1 Пароли хранятся как `str`, не `SecretStr`

| | |
|---|---|
| **Файл** | `src/utils/config.py:42-47` |
| **Проблема** | `smtp_password: str | None`, `imap_password: str | None` — Pydantic `SecretStr` не используется. Значения попадают в логи при `repr(config)`, в трейсбеки, в сериализацию. |
| **Риск** | HIGH |
| **Оценка** | 2 ч |

**Решение:** использовать `pydantic.SecretStr`, вызывать `.get_secret_value()` только в момент использования.

---

### 5.2 Нет `pip audit` / `safety` в CI

| | |
|---|---|
| **Файл** | `.github/workflows/ci.yml` |
| **Проблема** | Уязвимые зависимости не проверяются автоматически. `secret-scan.yml` есть, но аудит зависимостей отсутствует. |
| **Риск** | HIGH |
| **Оценка** | 2 ч |

**Решение:** добавить шаг `pip audit` или `trivy` в CI pipeline.

---

### 5.3 Credentials передаются как путь к файлу, нет поддержки environment secrets

| | |
|---|---|
| **Файл** | `src/integrations/google_sheets.py:108-119` |
| **Проблема** | Google credentials только через файл на диске. В Kubernetes/Docker Secrets, GitHub Actions — принято передавать содержимое как env var (base64). |
| **Риск** | MED |
| **Оценка** | 3 ч |

**Решение:** добавить `GOOGLE_SHEETS_CREDENTIALS_JSON` env var (base64 JSON), использовать `Credentials.from_service_account_info()`.

---

### 5.4 Rate limiting не реализован на уровне клиента

`_handle_rate_limit` в `base.py` только поднимает `RateLimitError` при HTTP 429, но не делает backoff автоматически. Нет глобального throttle — все вызовы идут без задержки.

**Риск:** MED
**Оценка:** 4 ч

---

### 5.5 `.gitleaks.toml` настроен, но gitleaks не запускается в CI

`.github/workflows/secret-scan.yml` существует. Нужно проверить, что он корректно интегрирован и не пропускает секреты.

**Оценка:** 2 ч

---

### 5.6 Нет pinning версий зависимостей (lock-file)

`pyproject.toml` использует `>=` для всех зависимостей без `uv.lock` или `requirements.lock`. В production возможна установка новой версии с breaking changes или CVE без ведома команды.

**Оценка:** 2 ч

---

**Итого Фаза 5: ~15 ч**

---

## Сводная таблица метрик

| Метрика | Сейчас | Production ready |
|---|---|---|
| Test coverage (total) | 75% | >85% |
| Unit tests | есть | есть |
| Integration tests | нет | есть (smoke tests для каждой интеграции) |
| mypy errors | 0 | 0 |
| ruff errors | 0 | 0 |
| CI на feature-ветках | нет | есть |
| CI на Python 3.11 + 3.12 | есть | есть |
| Dependency audit в CI | нет | есть (pip audit) |
| Secret scan в CI | настроен частично | активен и блокирует |
| Dependency lock-file | нет | `uv.lock` в репо |
| Пароли в конфиге | `str` (plain) | `SecretStr` |
| Credentials через env | нет | `GOOGLE_CREDENTIALS_JSON` base64 |
| Rate limiting (client-side) | raise only | auto-backoff + throttle |
| Correlation ID в логах | нет | есть |
| Health-check команда | нет | `upwork-learn health` |
| Метрики (Prometheus/аналог) | нет | есть |
| Sentry / error tracking | нет | есть |
| Runbook для деплоя | нет | есть в `docs/` |
| Makefile / единая точка входа | нет | есть |
| assert вместо if-raise | 4 места | 0 |
| Gmail hardcode в delete_email | есть | убран |
| configure_logging повторные вызовы | есть | 1 вызов при старте |

---

## Приоритетный порядок выполнения

```
Фаза 1 (~14 ч)   →   Фаза 5 (~15 ч)   →   Фаза 2 (~34 ч)   →   Фаза 3 (~22 ч)   →   Фаза 4 (~9.5 ч)
```

Стабильность и безопасность — перед надёжностью. Observability и DX — в последнюю очередь, но до публичного релиза.

**Общая оценка: ~95 ч** до production-ready состояния.
