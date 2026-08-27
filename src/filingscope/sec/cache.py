from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from filingscope.errors import CacheIntegrityError
from filingscope.schemas import RawFetchManifest

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_.=-]+$")


@dataclass(frozen=True, slots=True)
class CacheEntry:
    manifest: RawFetchManifest
    payload: bytes


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class RawResponseCache:
    """Content-addressed raw SEC cache with immutable per-content manifests."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def lookup(self, canonical_url: str) -> CacheEntry | None:
        index_path = self._index_path(canonical_url)
        if not index_path.exists():
            return None
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            manifest_path = self.root / index["manifest_path"]
            manifest = RawFetchManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8")
            )
            payload_path = self.root / manifest.relative_path
            payload = payload_path.read_bytes()
        except (OSError, KeyError, json.JSONDecodeError, ValueError):
            return None
        if sha256_bytes(payload) != manifest.content_sha256:
            return None
        return CacheEntry(manifest=manifest, payload=payload)

    def store(
        self,
        *,
        canonical_url: str,
        content: bytes,
        retrieved_at: datetime,
        http_status: int,
        content_type: str | None,
        etag: str | None,
        last_modified: str | None,
        namespace: str,
        identity: str,
        accession_number: str | None,
        attempt_count: int,
        cacheable: bool,
    ) -> CacheEntry:
        safe_namespace = self._safe_segment(namespace)
        safe_identity = self._safe_segment(identity)
        content_hash = sha256_bytes(content)
        extension = self._extension(content_type)
        relative_payload = (
            Path("raw/sec") / safe_namespace / safe_identity / (f"{content_hash}{extension}")
        )
        payload_path = self.root / relative_payload
        self._write_immutable(payload_path, content)

        manifest_id = hashlib.sha256(f"{canonical_url}\n{content_hash}".encode()).hexdigest()
        relative_manifest = Path("raw/sec/manifests") / f"{manifest_id}.json"
        manifest_path = self.root / relative_manifest
        manifest = RawFetchManifest(
            manifest_id=manifest_id,
            canonical_url=canonical_url,
            retrieved_at=retrieved_at,
            http_status=http_status,
            content_type=content_type,
            byte_length=len(content),
            etag=etag,
            last_modified=last_modified,
            content_sha256=content_hash,
            relative_path=relative_payload.as_posix(),
            accession_number=accession_number,
            attempt_count=attempt_count,
        )
        if manifest_path.exists():
            manifest = RawFetchManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8")
            )
        else:
            self._atomic_write(manifest_path, manifest.model_dump_json(indent=2).encode())

        if cacheable:
            index = json.dumps(
                {"manifest_path": relative_manifest.as_posix()},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            self._atomic_write(self._index_path(canonical_url), index)
        return CacheEntry(manifest=manifest, payload=content)

    def _index_path(self, canonical_url: str) -> Path:
        url_hash = hashlib.sha256(canonical_url.encode()).hexdigest()
        return self.root / "raw/sec/cache-index" / f"{url_hash}.json"

    @staticmethod
    def _safe_segment(value: str) -> str:
        if not _SAFE_SEGMENT.fullmatch(value):
            raise CacheIntegrityError(
                message=f"Unsafe cache path segment: {value!r}",
                code="unsafe_cache_path",
            )
        return value

    @staticmethod
    def _extension(content_type: str | None) -> str:
        if content_type and "json" in content_type.casefold():
            return ".json"
        if content_type and "html" in content_type.casefold():
            return ".html"
        return ".bin"

    @staticmethod
    def _write_immutable(path: Path, content: bytes) -> None:
        if path.exists():
            if path.read_bytes() != content:
                raise CacheIntegrityError(
                    message=f"Content-addressed payload mismatch at {path}",
                    code="cache_hash_collision",
                )
            return
        RawResponseCache._atomic_write(path, content)

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_bytes(content)
        os.replace(temporary, path)
