from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_CONTACT_PATTERN = re.compile(r"[^\s()<>]+@[^\s()<>]+\.[^\s()<>]+")
_PLACEHOLDERS = ("YOUR_NAME", "YOUR_EMAIL", "configure@", "example.invalid")


class Settings(BaseSettings):
    """Process configuration; operator identity and secrets remain environment-backed."""

    model_config = SettingsConfigDict(
        env_prefix="FILINGSCOPE_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["development", "test", "production"] = "development"
    data_dir: Path = Path("data")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    sec_user_agent: str | None = None
    sec_min_interval_seconds: float = Field(default=0.2, ge=0.1)
    sec_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    sec_cache_max_age_seconds: int = Field(default=86_400, ge=0)
    sec_max_response_bytes: int = Field(default=50_000_000, ge=1_024)
    groq_api_key: SecretStr | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_reasoning_model: str | None = None
    investigation_max_signals: int = Field(default=8, ge=1, le=10)
    investigation_max_evidence_packets: int = Field(default=12, ge=1, le=30)
    investigation_max_retries: int = Field(default=1, ge=0, le=3)
    investigation_wall_clock_seconds: int = Field(default=180, ge=10, le=900)

    @field_validator("sec_user_agent")
    @classmethod
    def validate_user_agent(cls, value: str | None) -> str | None:
        if value is None:
            return value
        candidate = value.strip()
        if len(candidate) < 12 or not _CONTACT_PATTERN.search(candidate):
            raise ValueError(
                "SEC User-Agent must identify the application and include contact email"
            )
        if any(placeholder.casefold() in candidate.casefold() for placeholder in _PLACEHOLDERS):
            raise ValueError("SEC User-Agent still contains a placeholder identity")
        return candidate

    def require_sec_user_agent(self) -> str:
        if self.sec_user_agent is None:
            raise ValueError(
                "FILINGSCOPE_SEC_USER_AGENT is required for SEC access; see .env.example"
            )
        return self.sec_user_agent
