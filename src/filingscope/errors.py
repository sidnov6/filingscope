from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class FilingScopeError(Exception):
    message: str
    code: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


class ConfigurationError(FilingScopeError):
    pass


class IdentityResolutionError(FilingScopeError):
    pass


class SecRequestError(FilingScopeError):
    pass


class SecPayloadError(FilingScopeError):
    pass


class CacheIntegrityError(FilingScopeError):
    pass


class StorageError(FilingScopeError):
    pass


class FilingParseError(FilingScopeError):
    pass


class RetrievalError(FilingScopeError):
    pass


class InvestigationError(FilingScopeError):
    pass
