"""Typed models for profiles, model payloads, and resolved settings."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    field_validator,
    model_validator,
)

ENV_PREFIX = "PRETEXT_"


class PretextError(Exception):
    """Base class for expected, user-facing failures."""


class ConfigError(PretextError):
    """Missing or contradictory configuration."""


class ProfileError(PretextError):
    """A profile file could not be read or validated."""


class APIError(PretextError):
    """The inference endpoint failed or returned something unusable."""


class Channel(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    SMS = "sms"
    CHAT = "chat"
    IN_PERSON = "in_person"
    LINKEDIN = "linkedin"


class Profile(BaseModel):
    """The persona a simulation is built around."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=80)
    role: str = Field(min_length=2, max_length=120)
    company: str = Field(min_length=2, max_length=120)
    communication_style: str = Field(min_length=3, max_length=280)
    department: str | None = Field(default=None, max_length=80)
    tenure: str | None = Field(
        default=None,
        max_length=60,
        description="How long the persona has held the role, e.g. '3 months'.",
    )
    reports_to: str | None = Field(default=None, max_length=80)
    systems: list[str] = Field(default_factory=list, max_length=12)
    notes: str | None = Field(default=None, max_length=600)

    @field_validator("systems")
    @classmethod
    def _clean_systems(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("systems contains duplicates")
        return cleaned

    @field_validator("department", "tenure", "reports_to", "notes")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class EscalationStep(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    stage: Annotated[int, Field(ge=1, le=12)]
    channel: Channel
    action: str = Field(min_length=10, max_length=600)
    goal: str = Field(min_length=5, max_length=300)
    artifact: str | None = Field(
        default=None,
        max_length=300,
        description="Concrete lure or prop used at this stage, if any.",
    )

    @field_validator("artifact", mode="before")
    @classmethod
    def _trim_artifact(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        trimmed = value.strip()
        return trimmed if len(trimmed) <= 300 else f"{trimmed[:297].rstrip()}..."

    @field_validator("stage", mode="before")
    @classmethod
    def _coerce_stage(cls, value: Any) -> Any:
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return value


class RedFlag(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=4, max_length=120)
    why_it_matters: str = Field(min_length=10, max_length=500)
    defender_action: str = Field(min_length=5, max_length=300)


class Simulation(BaseModel):
    """A complete, labeled simulation returned by the model."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    pretext: str = Field(min_length=80, max_length=2600)
    opening_message: str = Field(min_length=20, max_length=1800)
    subject_line: str | None = Field(default=None, max_length=140)
    escalation_path: list[EscalationStep] = Field(min_length=2, max_length=8)
    red_flags: list[RedFlag] = Field(min_length=2, max_length=8)
    difficulty: Annotated[int, Field(ge=1, le=5)] = 3
    objective: str = Field(default="", max_length=300)

    @field_validator("objective", mode="before")
    @classmethod
    def _trim_objective(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        trimmed = value.strip()
        return trimmed if len(trimmed) <= 300 else f"{trimmed[:297].rstrip()}..."

    @field_validator("opening_message")
    @classmethod
    def _strip_headers(cls, value: str) -> str:
        lines = value.splitlines()
        while lines and _is_header(lines[0]):
            lines.pop(0)
            while lines and not lines[0].strip():
                lines.pop(0)
        return "\n".join(lines).strip()

    @model_validator(mode="after")
    def _stages_are_ordered(self) -> Simulation:
        stages = [step.stage for step in self.escalation_path]
        if stages != list(range(1, len(stages) + 1)):
            raise ValueError(f"escalation_path stages must run 1..n in order, got {stages}")
        return self


HEADER_PREFIXES = ("subject:", "from:", "to:", "cc:", "sent:")


def _is_header(line: str) -> bool:
    return line.strip().lower().startswith(HEADER_PREFIXES)


class Settings(BaseModel):
    """Runtime configuration resolved from flags and environment."""

    model_config = ConfigDict(frozen=True)

    base_url: HttpUrl
    model: str = Field(min_length=1, max_length=120)
    api_key: str = Field(default="", repr=False)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    timeout: float = Field(default=60.0, gt=0, le=600)
    retries: int = Field(default=3, ge=0, le=8)
    max_tokens: int = Field(default=3200, ge=256, le=16000)
    seed: int | None = None

    @property
    def endpoint(self) -> str:
        return f"{str(self.base_url).rstrip('/')}/chat/completions"


DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"

PROVIDERS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "venice": "https://api.venice.ai/api/v1",
    "ollama": "http://localhost:11434/v1",
    "lmstudio": "http://localhost:1234/v1",
}
LOCAL_PROVIDERS = {"ollama", "lmstudio"}
ENV_FILE = ".env"


def _env(key: str) -> str | None:
    value = os.environ.get(key)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _dotenv_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    found: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip("'\"")
        if value:
            found[key.strip()] = value
    return found


def resolve_settings(
    *,
    provider: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    temperature: float | None = None,
    timeout: float | None = None,
    retries: int | None = None,
    max_tokens: int | None = None,
    seed: int | None = None,
    dotenv: Path | None = None,
) -> Settings:
    """Resolve settings with the precedence flag > env > .env > default."""

    file_values = _dotenv_values(dotenv or Path.cwd() / ENV_FILE)

    def pick(flag: str | None, env_name: str) -> str | None:
        if flag is not None and flag.strip():
            return flag.strip()
        key = ENV_PREFIX + env_name
        value = _env(key) or file_values.get(key)
        return value or None

    chosen = (provider or pick(None, "PROVIDER") or "").strip().lower() or None
    if chosen is not None and chosen not in PROVIDERS:
        raise ConfigError(f"unknown provider {chosen!r}; choose from {', '.join(PROVIDERS)}")

    resolved_url = pick(base_url, "BASE_URL")
    if resolved_url is None and chosen is not None:
        resolved_url = PROVIDERS[chosen]
    resolved_model = pick(model, "MODEL")
    resolved_key = pick(api_key, "API_KEY") or _env("OPENAI_API_KEY")
    if not resolved_key and chosen in LOCAL_PROVIDERS:
        resolved_key = "local"

    if resolved_url is None:
        resolved_url = DEFAULT_BASE_URL
    if resolved_model is None:
        resolved_model = DEFAULT_MODEL

    raw: dict[str, Any] = {
        "base_url": resolved_url,
        "model": resolved_model,
        "api_key": resolved_key or "",
    }
    for name, flag in (
        ("temperature", temperature),
        ("timeout", timeout),
        ("retries", retries),
        ("max_tokens", max_tokens),
        ("seed", seed),
    ):
        value = flag if flag is not None else pick(None, name.upper())
        if value is not None:
            raw[name] = value

    if raw["api_key"] == "":
        raise ConfigError("no API key: pass --api-key or set PRETEXT_API_KEY / OPENAI_API_KEY")

    try:
        return Settings(**raw)
    except ValidationError as exc:
        raise ConfigError(_format_validation(exc, prefix="invalid settings")) from exc


def _format_validation(exc: ValidationError, *, prefix: str) -> str:
    lines = [prefix]
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "<root>"
        lines.append(f"  {location}: {error['msg']}")
    return "\n".join(lines)


def load_profile(path: Path) -> Profile:
    """Read and validate a YAML profile."""

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProfileError(f"cannot read profile {path}: {exc.strerror or exc}") from exc

    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ProfileError(f"invalid YAML in {path}: {exc}") from exc

    if document is None:
        raise ProfileError(f"profile {path} is empty")
    if not isinstance(document, dict):
        raise ProfileError(f"profile {path} must be a YAML mapping, got {type(document).__name__}")

    try:
        return Profile.model_validate(document)
    except ValidationError as exc:
        raise ProfileError(_format_validation(exc, prefix=f"invalid profile {path}")) from exc


def profile_from_json(payload: str) -> Profile:
    try:
        return Profile.model_validate_json(payload)
    except ValidationError as exc:
        raise ProfileError(_format_validation(exc, prefix="invalid profile JSON")) from exc
