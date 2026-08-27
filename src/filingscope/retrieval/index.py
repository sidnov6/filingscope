from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from filingscope.errors import RetrievalError
from filingscope.schemas import FilingChunk

_TERM = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]+")


@dataclass(frozen=True, slots=True)
class SearchHit:
    chunk: FilingChunk
    score: Decimal


class FilingSearchIndex:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS filing_chunks "
                "(chunk_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS filing_chunks_fts USING fts5("
                "chunk_id UNINDEXED, cik UNINDEXED, accession_number UNINDEXED, "
                "form UNINDEXED, section, subsection, text, tokenize='porter unicode61')"
            )

    def index(self, chunks: tuple[FilingChunk, ...] | list[FilingChunk]) -> None:
        try:
            with sqlite3.connect(self.database_path) as connection:
                for chunk in chunks:
                    connection.execute(
                        "INSERT OR REPLACE INTO filing_chunks VALUES (?, ?)",
                        (chunk.chunk_id, chunk.model_dump_json()),
                    )
                    connection.execute(
                        "DELETE FROM filing_chunks_fts WHERE chunk_id = ?", (chunk.chunk_id,)
                    )
                    connection.execute(
                        "INSERT INTO filing_chunks_fts "
                        "(chunk_id, cik, accession_number, form, section, subsection, text) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            chunk.chunk_id,
                            chunk.cik,
                            chunk.accession_number,
                            chunk.form,
                            chunk.section,
                            chunk.subsection or "",
                            chunk.text,
                        ),
                    )
        except sqlite3.Error as error:
            raise RetrievalError(
                message="Filing search index update failed",
                code="retrieval_index_failed",
                details={"reason": str(error)},
            ) from error

    def search(
        self,
        query: str,
        *,
        cik: str,
        forms: tuple[str, ...] = (),
        accessions: tuple[str, ...] = (),
        sections: tuple[str, ...] = (),
        limit: int = 10,
    ) -> tuple[SearchHit, ...]:
        match_query = _match_query(query)
        if not match_query:
            return ()
        clauses = ["filing_chunks_fts MATCH ?", "filing_chunks_fts.cik = ?"]
        parameters: list[object] = [match_query, cik]
        for field, values in (
            ("form", forms),
            ("accession_number", accessions),
            ("section", sections),
        ):
            if values:
                placeholders = ", ".join("?" for _ in values)
                clauses.append(f"filing_chunks_fts.{field} IN ({placeholders})")
                parameters.extend(values)
        parameters.append(limit)
        sql = (
            "SELECT c.payload_json, bm25(filing_chunks_fts, 0, 0, 0, 0, 2, 1, 5) AS rank "
            "FROM filing_chunks_fts JOIN filing_chunks c USING (chunk_id) WHERE "
            + " AND ".join(clauses)
            + " ORDER BY rank, filing_chunks_fts.chunk_id LIMIT ?"
        )
        try:
            with sqlite3.connect(self.database_path) as connection:
                rows = connection.execute(sql, parameters).fetchall()
        except sqlite3.Error as error:
            raise RetrievalError(
                message="Filing search query failed",
                code="retrieval_query_failed",
                details={"reason": str(error)},
            ) from error
        return tuple(
            SearchHit(
                chunk=FilingChunk.model_validate(json.loads(payload)),
                score=Decimal(str(-rank)),
            )
            for payload, rank in rows
        )


def _match_query(query: str) -> str:
    tokens = []
    for token in _TERM.findall(query.casefold()):
        if token not in tokens:
            tokens.append(token)
    return " OR ".join(f'"{token}"' for token in tokens[:24])
