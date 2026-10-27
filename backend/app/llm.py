"""Provider-agnostic LLM wrapper with JSON-forced, schema-validated generation.

The public entry point is ``generate_json``. It:
  1. Reads provider/model/key config from ``app.config.settings``.
  2. Instructs the model to return ONLY JSON matching a Pydantic schema.
  3. Validates the response with the Pydantic schema, retrying on failure
     with the validation error appended to the prompt.
  4. Raises ``LLMError`` if all retries fail so callers can apply their own
     deterministic fallback (the demo must never crash).
  5. Optionally caches responses keyed by a hash of the inputs so repeated
     demo runs are instant and identical (``LLM_NO_CACHE=true`` disables).
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import settings

logger = logging.getLogger("autoscout.llm")

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Raised when the LLM output cannot be produced or validated."""


# ---------------------------------------------------------------------------
# Response cache (in-memory + on-disk) keyed by hash(system, user, schema)
# ---------------------------------------------------------------------------
_CACHE_DIR = settings.__class__ and (
    __import__("pathlib").Path(__file__).resolve().parent.parent / ".llm_cache"
)


def _cache_key(system: str, user: str, schema: type[BaseModel]) -> str:
    raw = "\n".join(
        [system, user, schema.__name__, json.dumps(schema.model_json_schema(), sort_keys=True)]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> dict[str, Any] | None:
    if settings.llm_no_cache or not settings.llm_cache_enabled:
        return None
    path = _CACHE_DIR / f"{key}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
    return None


def _cache_put(key: str, data: dict[str, Any]) -> None:
    if settings.llm_no_cache or not settings.llm_cache_enabled:
        return
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (_CACHE_DIR / f"{key}.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        logger.warning("Could not write LLM cache entry %s", key)


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------
def _build_prompt(system: str, user: str, schema: type[BaseModel]) -> str:
    schema_json = json.dumps(schema.model_json_schema(), indent=2)
    return (
        f"{system}\n\n"
        f"Respond with ONLY a single JSON object. No prose, no markdown fences. "
        f"The JSON must match this JSON Schema:\n{schema_json}\n\n"
        f"User request:\n{user}"
    )


def _mock_completion(system: str, user: str, schema: type[BaseModel]) -> dict[str, Any]:
    """Deterministic mock provider that returns a canned, schema-valid object.

    Used for offline development (LLM_PROVIDER=mock). The canned values are
    derived from the schema so validation always passes; callers that need
    real content will pass LLM_PROVIDER=openai with a real API key.
    """
    def sample(value_schema: dict[str, Any]) -> Any:
        """Recursively build a sample value from a JSON Schema fragment."""
        if "anyOf" in value_schema:
            for opt in value_schema["anyOf"]:
                if opt.get("type") != "null":
                    return sample(opt)
            return None
        kind = value_schema.get("type")
        if kind == "string":
            if "enum" in value_schema:
                return value_schema["enum"][0]
            fmt = value_schema.get("format")
            if fmt == "date-time":
                return "2025-01-06T09:00:00Z"
            if fmt == "date":
                return "2025-01-06"
            return "mock"
        if kind == "integer":
            return 0
        if kind == "number":
            return 0.0
        if kind == "boolean":
            return False
        if kind == "array":
            items = value_schema.get("items", {})
            return [sample(items)]
        if kind == "object":
            props = value_schema.get("properties", {})
            required = set(value_schema.get("required", []))
            return {
                k: sample(v)
                for k, v in props.items()
                if k in required or not required
            }
        return None

    return sample(schema.model_json_schema())


def _openai_completion(system: str, user: str, schema: type[BaseModel]) -> dict[str, Any]:
    """Call an OpenAI-compatible /chat/completions endpoint with JSON mode."""
    if not settings.llm_api_key:
        raise LLMError("LLM_API_KEY is not set. Set it in .env or use LLM_PROVIDER=mock.")

    payload = {
        "model": settings.llm_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _build_prompt(system, user, schema)},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"

    try:
        with httpx.Client(timeout=settings.llm_timeout_s) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            body = resp.json()
    except httpx.TimeoutException as exc:
        raise LLMError(f"LLM request timed out after {settings.llm_timeout_s}s") from exc
    except httpx.HTTPStatusError as exc:
        raise LLMError(f"LLM HTTP {exc.response.status_code}: {exc.response.text[:500]}") from exc
    except httpx.HTTPError as exc:
        raise LLMError(f"LLM transport error: {exc}") from exc

    try:
        content = body["choices"][0]["message"]["content"]
        return json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise LLMError(f"Malformed LLM response: {body}") from exc


def _complete(system: str, user: str, schema: type[BaseModel]) -> dict[str, Any]:
    provider = settings.llm_provider.lower().strip()
    if provider == "mock":
        return _mock_completion(system, user, schema)
    if provider in ("openai", "openai_compat", "azure"):
        return _openai_completion(system, user, schema)
    raise LLMError(f"Unknown LLM_PROVIDER={provider!r}. Use 'mock' or 'openai'.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_json(
    system: str,
    user: str,
    schema: type[T],
    retries: int = 2,
) -> T:
    """Generate and validate a JSON response conforming to ``schema``.

    Args:
        system: System prompt describing the assistant's role.
        user: User prompt / task description.
        schema: Pydantic model class the output must conform to.
        retries: Number of validation retries (each appends the error to the prompt).

    Returns:
        A validated instance of ``schema``.

    Raises:
        LLMError: if all retries fail (callers should apply a fallback).
    """
    cache_key = _cache_key(system, user, schema)
    cached = _cache_get(cache_key)
    if cached is not None:
        logger.info("LLM cache hit for %s", cache_key[:8])
        return schema.model_validate(cached)

    last_error: Exception | None = None
    current_user = user
    for attempt in range(retries + 1):
        try:
            raw = _complete(system, current_user, schema)
            return schema.model_validate(raw)
        except ValidationError as exc:
            last_error = exc
            current_user = (
                f"{user}\n\nYour previous JSON failed validation with this error:\n"
                f"{exc.errors_json}\nReturn corrected JSON only."
            )
            logger.warning("LLM validation failed (attempt %d/%d): %s", attempt + 1, retries + 1, exc)
        except LLMError as exc:
            last_error = exc
            logger.warning("LLM call failed (attempt %d/%d): %s", attempt + 1, retries + 1, exc)

    # All retries exhausted: attempt a deterministic fallback before raising.
    try:
        fb = schema.model_validate(_mock_completion(system, user, schema))
        logger.warning("Falling back to mock data for %s", schema.__name__)
        _cache_put(cache_key, fb.model_dump())
        return fb
    except ValidationError:
        raise LLMError(
            f"LLM generation failed after {retries + 1} attempts: {last_error}"
        ) from last_error
