from __future__ import annotations

import pytest
from pydantic import ValidationError

from filingscope.config import Settings


def test_configuration_accepts_identifiable_sec_user_agent() -> None:
    settings = Settings(sec_user_agent="FilingScope/0.1 analyst@firm.test")
    assert settings.require_sec_user_agent().startswith("FilingScope/")
    assert settings.sec_min_interval_seconds >= 0.1


@pytest.mark.parametrize(
    "value",
    ["FilingScope", "FilingScope YOUR_EMAIL", "FilingScope configure@example.invalid"],
)
def test_configuration_rejects_unidentifiable_sec_user_agent(value: str) -> None:
    with pytest.raises(ValidationError):
        Settings(sec_user_agent=value)


def test_configuration_requires_identity_only_when_sec_access_is_requested() -> None:
    with pytest.raises(ValueError, match="FILINGSCOPE_SEC_USER_AGENT"):
        Settings(_env_file=None).require_sec_user_agent()
