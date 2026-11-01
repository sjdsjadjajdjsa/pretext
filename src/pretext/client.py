"""HTTP client for any OpenAI-compatible chat completions endpoint."""

from __future__ import annotations

import json
import random
import time
from typing import Any

import httpx
from pydantic import ValidationError

from .models import APIError, Settings, Simulation, _format_validation
from .prompt import build_payload_messages

RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
MAX_RETRY_AFTER = 30.0
USER_AGENT = "pretext/0.1 (+authorized-training)"


def extract_json(content: str) -> dict[str, Any]:
    """Pull a JSON object out of model output that may be wrapped or fenced."""

    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
        text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise APIError(
                "model returned no JSON object; first 200 chars: "
                f"{content.strip()[:200]!r}"
            ) from None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise APIError(f"model returned malformed JSON: {exc}") from None

    if not isinstance(parsed, dict):
        raise APIError(f"expected a JSON object, got {type(parsed).__name__}")
    return parsed


def _content_of(body: dict[str, Any]) -> str:
    try:
        choice = body["choices"][0]
        message = choice["message"]
        content = message["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise APIError(f"unexpected response shape: {str(body)[:200]}") from exc

    if isinstance(content, list):
        pieces = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") in (None, "text")
        ]
        content = "".join(pieces)

    if not isinstance(content, str) or not content.strip():
        raise APIError("model returned empty content")
    return content


class Client:
    def __init__(self, settings: Settings, *, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport
        self.last_usage: dict[str, Any] | None = None

    def _payload(self, profile, channel: str | None, extra: str | None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": build_payload_messages(profile, channel=channel, extra=extra),
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
            "response_format": {"type": "json_object"},
        }
        if self.settings.seed is not None:
            payload["seed"] = self.settings.seed
        return payload

    def generate(
        self,
        profile,
        *,
        channel: str | None = None,
        extra: str | None = None,
    ) -> Simulation:
        body = self._request(self._payload(profile, channel, extra))
        raw = extract_json(_content_of(body))
        try:
            return Simulation.model_validate(raw)
        except ValidationError as exc:
            raise APIError(
                _format_validation(exc, prefix="model output failed validation")
            ) from exc

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }
        attempts = self.settings.retries + 1
        last: APIError | None = None

        with httpx.Client(
            timeout=self.settings.timeout,
            transport=self._transport,
            follow_redirects=True,
        ) as client:
            for attempt in range(1, attempts + 1):
                try:
                    response = client.post(
                        self.settings.endpoint, json=payload, headers=headers
                    )
                except httpx.TimeoutException as exc:
                    last = APIError(f"request timed out after {self.settings.timeout:g}s")
                    if attempt < attempts:
                        time.sleep(_backoff(attempt, None))
                        continue
                    raise last from exc
                except httpx.HTTPError as exc:
                    last = APIError(f"connection failed: {exc}")
                    if attempt < attempts:
                        time.sleep(_backoff(attempt, None))
                        continue
                    raise last from exc

                if response.status_code in RETRY_STATUS and attempt < attempts:
                    time.sleep(_backoff(attempt, response.headers.get("retry-after")))
                    last = APIError(f"HTTP {response.status_code} from endpoint")
                    continue

                last = None
                body = _decode(response)
                usage = body.get("usage")
                self.last_usage = usage if isinstance(usage, dict) else None
                return body
        raise last or APIError("request failed")


def _backoff(attempt: int, retry_after: str | None) -> float:
    if retry_after:
        try:
            return min(float(retry_after), MAX_RETRY_AFTER)
        except ValueError:
            pass
    return min(0.5 * 2 ** (attempt - 1), 8.0) * (0.8 + random.random() * 0.4)


def _decode(response: httpx.Response) -> dict[str, Any]:
    if response.status_code >= 400:
        raise APIError(f"HTTP {response.status_code}: {_error_text(response)}")
    try:
        body = response.json()
    except (json.JSONDecodeError, httpx.DecodingError):
        raise APIError(f"endpoint returned non-JSON: {response.text[:200]!r}") from None
    if not isinstance(body, dict):
        raise APIError("endpoint returned a non-object body")
    return body


def _error_text(response: httpx.Response) -> str:
    try:
        body = response.json()
    except (ValueError, httpx.DecodingError):
        return response.text.strip()[:300] or "<empty body>"
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])[:300]
        if isinstance(error, str):
            return error[:300]
        if body.get("message"):
            return str(body["message"])[:300]
    return str(body)[:300]
