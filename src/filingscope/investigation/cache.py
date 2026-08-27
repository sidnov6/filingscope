from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

OutputT = TypeVar("OutputT", bound=BaseModel)


class AgentOutputCache:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir

    @staticmethod
    def key(material: dict[str, object]) -> str:
        serialized = json.dumps(material, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode()).hexdigest()

    def load(self, key: str, model: type[OutputT]) -> OutputT | None:
        path = self.cache_dir / f"{key}.json"
        if not path.exists():
            return None
        try:
            return model.model_validate_json(path.read_text())
        except (OSError, ValidationError):
            return None

    def store(self, key: str, output: BaseModel) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / f"{key}.json"
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(output.model_dump_json(indent=2))
        os.replace(temporary, path)
