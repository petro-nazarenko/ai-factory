"""Centralized LLM Router — workspace/llm_router.py

Providers  : Groq, Cerebras, Together AI, Mistral  (all OpenAI-compatible REST)
Task types : scoring | generation | validation | roadmap | gtm
Routing    : task → preferred provider → TPM/TPD check → 429 fallback chain

Usage (sync):
    from workspace.llm_router import router
    text = router.complete("scoring", "Score this idea: ...")

Usage (async):
    from workspace.llm_router import router
    text = await router.acomplete("generation", "Generate 3 ideas for ...")

Import from subdirectory:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../workspace"))
    from llm_router import router
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Deque

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# .env loader — runs once at import time
# ---------------------------------------------------------------------------

_ENV_SEARCH_PATHS = [
    # Relative to workspace/ (where this file lives)
    Path(__file__).resolve().parent.parent / "Moneymaker" / ".env",
    Path(__file__).resolve().parent.parent / ".env",
    Path(__file__).resolve().parent / ".env",
]

_PROVIDER_KEYS = ("GROQ_API_KEY", "CEREBRAS_API_KEY", "TOGETHER_API_KEY", "MISTRAL_API_KEY")


def _load_dotenv(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict. Ignores comments and blank lines."""
    result: dict[str, str] = {}
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            # Strip inline comments: KEY=value  # comment
            line = re.sub(r"\s+#.*$", "", line)
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            result[key] = val
    except OSError:
        pass
    return result


def _bootstrap_env() -> None:
    """Load provider API keys from .env files into os.environ (env vars win)."""
    loaded_from: str | None = None
    dotenv: dict[str, str] = {}

    for candidate in _ENV_SEARCH_PATHS:
        if candidate.exists():
            dotenv = _load_dotenv(candidate)
            loaded_from = str(candidate)
            break

    # Only set keys that are absent from the real environment
    injected: list[str] = []
    for key in _PROVIDER_KEYS:
        if not os.environ.get(key) and dotenv.get(key):
            os.environ[key] = dotenv[key]
            injected.append(key)

    # Debug output — always print so the user can see what was found
    found = [k for k in _PROVIDER_KEYS if os.environ.get(k)]
    missing = [k for k in _PROVIDER_KEYS if not os.environ.get(k)]

    if loaded_from:
        print(f"[LLMRouter] .env loaded: {loaded_from}")
        if injected:
            print(f"[LLMRouter] Keys injected from .env : {injected}")
    else:
        print(f"[LLMRouter] No .env file found (searched {len(_ENV_SEARCH_PATHS)} paths)")

    print(f"[LLMRouter] Keys available : {found}")
    if missing:
        print(f"[LLMRouter] Keys missing   : {missing}")


_bootstrap_env()

# ---------------------------------------------------------------------------
# Provider configs
# ---------------------------------------------------------------------------

@dataclass
class ProviderConfig:
    name: str
    env_key: str                    # env var name for the API key
    base_url: str
    models: list[str]               # index 0 = preferred, 1 = lighter fallback
    tpm_limit: int                  # tokens per minute (0 = unlimited)
    tpd_limit: int                  # tokens per day    (0 = unlimited)

    @property
    def api_key(self) -> str:
        return os.getenv(self.env_key, "")

    @property
    def available(self) -> bool:
        return bool(self.api_key)


PROVIDERS: dict[str, ProviderConfig] = {
    "groq": ProviderConfig(
        name="groq",
        env_key="GROQ_API_KEY",
        base_url="https://api.groq.com/openai/v1",
        models=["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        tpm_limit=6_000,        # free tier: 6k TPM
        tpd_limit=500_000,      # free tier: 500k TPD
    ),
    "cerebras": ProviderConfig(
        name="cerebras",
        env_key="CEREBRAS_API_KEY",
        base_url="https://api.cerebras.ai/v1",  # used for display only; SDK handles transport
        models=["llama3.1-8b", "llama3.1-8b"],  # SDK-only provider; both slots same model
        tpm_limit=60_000,       # ~60k TPM (fast inference chip)
        tpd_limit=1_000_000,
    ),
    "together": ProviderConfig(
        name="together",
        env_key="TOGETHER_API_KEY",
        base_url="https://api.together.xyz/v1",
        models=["meta-llama/Llama-3.3-70B-Instruct-Turbo", "meta-llama/Llama-3.2-3B-Instruct-Turbo"],
        tpm_limit=0,            # pay-as-you-go, no hard TPM
        tpd_limit=0,
    ),
    "mistral": ProviderConfig(
        name="mistral",
        env_key="MISTRAL_API_KEY",
        base_url="https://api.mistral.ai/v1",
        models=["mistral-small-latest", "mistral-tiny"],
        tpm_limit=0,            # pay-as-you-go
        tpd_limit=0,
    ),
}

# ---------------------------------------------------------------------------
# Task configs
# ---------------------------------------------------------------------------

@dataclass
class TaskConfig:
    preferred_provider: str     # first provider to try
    preferred_model: str        # model for this task
    min_model: str              # lighter model on retry/fallback
    max_tokens: int
    system_prompt: str = "You are a helpful assistant. Be concise and precise."


# Provider order for each task type when preferred is unavailable/rate-limited
_FALLBACK_ORDER: dict[str, list[str]] = {
    "scoring":    ["groq",    "cerebras", "mistral",  "together"],
    "generation": ["cerebras","together", "groq",     "mistral"],
    "validation": ["mistral", "groq",     "cerebras", "together"],
    "roadmap":    ["together","mistral",  "cerebras", "groq"],
    "gtm":        ["together","mistral",  "groq",     "cerebras"],
}

TASKS: dict[str, TaskConfig] = {
    "scoring": TaskConfig(
        preferred_provider="groq",
        preferred_model="llama-3.3-70b-versatile",
        min_model="llama-3.1-8b-instant",
        max_tokens=512,
        system_prompt=(
            "You are a scoring engine. Return only a JSON object with numeric scores. "
            "No explanation, no markdown."
        ),
    ),
    "generation": TaskConfig(
        preferred_provider="cerebras",
        preferred_model="llama3.3-70b",
        min_model="llama3.1-8b",
        max_tokens=2048,
        system_prompt=(
            "You are an expert idea generator. Return only raw JSON arrays or objects. "
            "No markdown, no explanation."
        ),
    ),
    "validation": TaskConfig(
        preferred_provider="mistral",
        preferred_model="mistral-small-latest",
        min_model="mistral-tiny",
        max_tokens=2048,
        system_prompt=(
            "You are a strict schema validator. Return only a JSON object with "
            "'valid': bool and 'errors': [string]. No extra text."
        ),
    ),
    "roadmap": TaskConfig(
        preferred_provider="together",
        preferred_model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        min_model="meta-llama/Llama-3.2-3B-Instruct-Turbo",
        max_tokens=4096,
        system_prompt=(
            "You are a product roadmap architect. Produce detailed, structured roadmaps. "
            "Return only raw JSON."
        ),
    ),
    "gtm": TaskConfig(
        preferred_provider="together",
        preferred_model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        min_model="meta-llama/Llama-3.2-3B-Instruct-Turbo",
        max_tokens=2048,
        system_prompt=(
            "You are a GTM strategist. Produce concise go-to-market plans. "
            "Return only raw JSON."
        ),
    ),
}

# ---------------------------------------------------------------------------
# Usage tracker (per provider)
# ---------------------------------------------------------------------------

def _estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token ≈ 4 characters."""
    return max(1, len(text) // 4)


@dataclass
class UsageTracker:
    """Sliding-window TPM and daily TPD tracker."""
    tpm_limit: int
    tpd_limit: int
    _minute_window: Deque[tuple[float, int]] = field(default_factory=deque)
    _day_total: int = 0
    _day_date: date = field(default_factory=date.today)
    # When a 429 is received, block this provider until this timestamp
    _blocked_until: float = 0.0

    def _refresh_day(self) -> None:
        today = date.today()
        if today != self._day_date:
            self._day_date = today
            self._day_total = 0

    def _tokens_last_minute(self) -> int:
        now = time.monotonic()
        cutoff = now - 60.0
        while self._minute_window and self._minute_window[0][0] < cutoff:
            self._minute_window.popleft()
        return sum(t for _, t in self._minute_window)

    def is_blocked(self) -> bool:
        """True if provider is in 429 cooldown."""
        return time.monotonic() < self._blocked_until

    def would_exceed(self, estimated_tokens: int) -> bool:
        """True if sending *estimated_tokens* would breach TPM or TPD."""
        self._refresh_day()
        if self.tpm_limit and (self._tokens_last_minute() + estimated_tokens) > self.tpm_limit:
            return True
        if self.tpd_limit and (self._day_total + estimated_tokens) > self.tpd_limit:
            return True
        return False

    def record(self, tokens_used: int) -> None:
        """Record actual token usage after a successful call."""
        self._refresh_day()
        self._day_total += tokens_used
        self._minute_window.append((time.monotonic(), tokens_used))

    def mark_rate_limited(self, cooldown_seconds: float = 60.0) -> None:
        """Block provider for *cooldown_seconds* after a 429."""
        self._blocked_until = time.monotonic() + cooldown_seconds
        logger.warning("Provider rate-limited — cooling down for %.0fs", cooldown_seconds)

    @property
    def stats(self) -> dict:
        self._refresh_day()
        return {
            "tpm_used": self._tokens_last_minute(),
            "tpd_used": self._day_total,
            "blocked_for": max(0.0, self._blocked_until - time.monotonic()),
        }


# ---------------------------------------------------------------------------
# Low-level call helpers
# ---------------------------------------------------------------------------

def _cerebras_call_sync(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
) -> tuple[str, int]:
    """Call Cerebras via its official SDK (sync). Returns (text, tokens_used).

    Using the SDK instead of raw httpx because Cerebras blocks plain REST calls
    and requires their client library for correct auth/transport handling.
    """
    try:
        import cerebras.cloud.sdk as cb
    except ImportError as exc:
        raise RuntimeError(
            "cerebras-cloud-sdk not installed. Run: pip install cerebras-cloud-sdk"
        ) from exc

    client = cb.Cerebras(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        )
    except Exception as exc:
        status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
        if status == 429 or type(exc).__name__ == "RateLimitError":
            raise _RateLimitError("cerebras") from exc
        raise

    choices = getattr(response, "choices", None) or []
    text = choices[0].message.content or "" if choices else ""  # type: ignore[union-attr]
    tokens_used = (
        getattr(getattr(response, "usage", None), "total_tokens", None)
        or _estimate_tokens(user_prompt + system_prompt)
    )
    return text, int(tokens_used)


def _httpx_call_sync(
    base_url: str,
    api_key: str,
    provider_name: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
) -> tuple[str, int]:
    """Call any OpenAI-compatible REST provider synchronously. Returns (text, tokens_used)."""
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            f"{base_url}/chat/completions",
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    if resp.status_code == 429:
        raise _RateLimitError(provider_name)

    resp.raise_for_status()
    data = resp.json()
    usage = data.get("usage") or {}
    tokens_used = usage.get("total_tokens") or _estimate_tokens(user_prompt + system_prompt)
    choices = data.get("choices") or []
    if not choices:
        raise ValueError(f"Empty choices from {provider_name}")
    text = (choices[0].get("message") or {}).get("content") or ""
    return text, int(tokens_used)


async def _httpx_call_async(
    base_url: str,
    api_key: str,
    provider_name: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
) -> tuple[str, int]:
    """Async version of _httpx_call_sync. Creates a fresh client per call
    to avoid event-loop binding issues when called from multiple asyncio.run()
    invocations."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    if resp.status_code == 429:
        raise _RateLimitError(provider_name)

    resp.raise_for_status()
    data = resp.json()
    usage = data.get("usage") or {}
    tokens_used = usage.get("total_tokens") or _estimate_tokens(user_prompt + system_prompt)
    choices = data.get("choices") or []
    if not choices:
        raise ValueError(f"Empty choices from {provider_name}")
    text = (choices[0].get("message") or {}).get("content") or ""
    return text, int(tokens_used)


# ---------------------------------------------------------------------------
# LLM Router
# ---------------------------------------------------------------------------

class LLMRouter:
    """Task-aware LLM router with per-provider TPM/TPD tracking and 429 fallback.

    complete()  — fully synchronous, no asyncio dependency, safe to call
                  repeatedly without event-loop lifecycle concerns.
    acomplete() — async variant for use inside async callers (idea_generator).

    Attributes:
        providers   -- ProviderConfig registry (read-only after init)
        tasks       -- TaskConfig registry (read-only after init)
        usage       -- per-provider UsageTracker instances
    """

    def __init__(
        self,
        providers: dict[str, ProviderConfig] | None = None,
        tasks: dict[str, TaskConfig] | None = None,
    ) -> None:
        self.providers = providers or PROVIDERS
        self.tasks = tasks or TASKS
        self.usage: dict[str, UsageTracker] = {
            name: UsageTracker(tpm_limit=p.tpm_limit, tpd_limit=p.tpd_limit)
            for name, p in self.providers.items()
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _provider_order(self, task_type: str) -> list[str]:
        """Return provider names in priority order for this task."""
        order = _FALLBACK_ORDER.get(task_type, list(self.providers.keys()))
        return [p for p in order if p in self.providers]

    def _pick_model(self, provider_name: str, task: TaskConfig, use_min: bool = False) -> str:
        """Return the appropriate model for this provider/task combination."""
        p = self.providers[provider_name]
        target = task.min_model if use_min else task.preferred_model
        return target if target in p.models else p.models[0]

    def _dispatch_sync(
        self,
        provider_name: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
    ) -> tuple[str, int]:
        """Route a sync call to the correct backend for *provider_name*."""
        p = self.providers[provider_name]
        if provider_name == "cerebras":
            return _cerebras_call_sync(
                p.api_key, model, system_prompt, user_prompt, max_tokens
            )
        return _httpx_call_sync(
            p.base_url, p.api_key, provider_name,
            model, system_prompt, user_prompt, max_tokens,
        )

    async def _dispatch_async(
        self,
        provider_name: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
    ) -> tuple[str, int]:
        """Route an async call to the correct backend for *provider_name*."""
        p = self.providers[provider_name]
        if provider_name == "cerebras":
            # Cerebras SDK is sync-only; run in a thread to avoid blocking the loop.
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: _cerebras_call_sync(
                    p.api_key, model, system_prompt, user_prompt, max_tokens
                ),
            )
        return await _httpx_call_async(
            p.base_url, p.api_key, provider_name,
            model, system_prompt, user_prompt, max_tokens,
        )

    def _iter_candidates(
        self, task_type: str, prompt: str
    ):
        """Yield (provider_name, model, tracker) for each viable candidate."""
        task = self.tasks[task_type]
        for provider_name in self._provider_order(task_type):
            p = self.providers[provider_name]
            if not p.available:
                logger.debug("Router: %s not configured — skipping", provider_name)
                continue
            tracker = self.usage[provider_name]
            if tracker.is_blocked():
                logger.debug("Router: %s in 429 cooldown — skipping", provider_name)
                continue
            est = _estimate_tokens(prompt)
            if tracker.would_exceed(est):
                logger.info("Router: %s near limit (est %d tokens) — skipping", provider_name, est)
                continue
            use_min = provider_name != task.preferred_provider
            model = self._pick_model(provider_name, task, use_min=use_min)
            yield provider_name, model, tracker

    # ------------------------------------------------------------------
    # Public sync interface  (truly sync — no asyncio)
    # ------------------------------------------------------------------

    def complete(
        self,
        task_type: str,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Synchronous completion. No event loop required — safe to call
        multiple times in sequence without 'event loop closed' errors.

        Raises:
            LLMRouterError  if all providers fail.
            KeyError        if task_type is unknown.
        """
        task = self.tasks[task_type]
        effective_system = system_prompt if system_prompt is not None else task.system_prompt
        errors: dict[str, str] = {}

        for provider_name, model, tracker in self._iter_candidates(task_type, prompt):
            try:
                logger.info("Router[sync]: %s/%s → %s", provider_name, model, task_type)
                text, tokens_used = self._dispatch_sync(
                    provider_name, model, effective_system, prompt, task.max_tokens
                )
                tracker.record(tokens_used)
                if text:
                    return text
                logger.warning("Router[sync]: %s returned empty — trying next", provider_name)

            except _RateLimitError:
                tracker.mark_rate_limited(cooldown_seconds=60.0)
                errors[provider_name] = "429 rate limit"

            except Exception as exc:
                errors[provider_name] = str(exc)
                logger.error("Router[sync]: %s error: %s — trying next", provider_name, exc)

        raise LLMRouterError(task_type, errors)

    # ------------------------------------------------------------------
    # Public async interface
    # ------------------------------------------------------------------

    async def acomplete(
        self,
        task_type: str,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Async completion. Uses thread executor for SDK-based providers
        (Cerebras) and async httpx for REST providers.

        Raises:
            LLMRouterError  if all providers fail.
            KeyError        if task_type is unknown.
        """
        task = self.tasks[task_type]
        effective_system = system_prompt if system_prompt is not None else task.system_prompt
        errors: dict[str, str] = {}

        for provider_name, model, tracker in self._iter_candidates(task_type, prompt):
            try:
                logger.info("Router[async]: %s/%s → %s", provider_name, model, task_type)
                text, tokens_used = await self._dispatch_async(
                    provider_name, model, effective_system, prompt, task.max_tokens
                )
                tracker.record(tokens_used)
                if text:
                    return text
                logger.warning("Router[async]: %s returned empty — trying next", provider_name)

            except _RateLimitError:
                tracker.mark_rate_limited(cooldown_seconds=60.0)
                errors[provider_name] = "429 rate limit"

            except Exception as exc:
                errors[provider_name] = str(exc)
                logger.error("Router[async]: %s error: %s — trying next", provider_name, exc)

        raise LLMRouterError(task_type, errors)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def status(self) -> dict:
        """Return current availability and usage stats for all providers."""
        result = {}
        for name, p in self.providers.items():
            result[name] = {
                "available": p.available,
                "models": p.models,
                **self.usage[name].stats,
            }
        return result


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class _RateLimitError(Exception):
    """Internal signal — provider returned HTTP 429."""
    def __init__(self, provider: str) -> None:
        super().__init__(f"{provider} rate limited (429)")
        self.provider = provider


class LLMRouterError(Exception):
    """Raised when all providers fail for a task."""
    def __init__(self, task_type: str, errors: dict[str, str]) -> None:
        tried = ", ".join(f"{k}: {v}" for k, v in errors.items()) or "none available"
        super().__init__(f"LLMRouter: all providers failed for '{task_type}' — {tried}")
        self.task_type = task_type
        self.errors = errors


# ---------------------------------------------------------------------------
# Singleton — import this
# ---------------------------------------------------------------------------

router = LLMRouter()
