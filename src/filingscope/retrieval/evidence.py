from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from decimal import Decimal

from filingscope.retrieval.index import FilingSearchIndex, SearchHit
from filingscope.schemas import EvidencePacket, Signal

_TERM = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]+")


class EvidenceBuilder:
    def __init__(self, index: FilingSearchIndex, *, max_packets: int = 12) -> None:
        self.index = index
        self.max_packets = max_packets

    def for_signals(
        self,
        cik: str,
        signals: Sequence[Signal],
    ) -> tuple[EvidencePacket, ...]:
        packets: list[EvidencePacket] = []
        seen_chunks: set[str] = set()
        for signal in signals:
            query = " ".join([signal.test_id.replace("_", " "), *signal.evidence_requirements])
            for hit in self.index.search(query, cik=cik, limit=8):
                if hit.chunk.chunk_id in seen_chunks:
                    continue
                packets.append(self._packet(signal, hit, query))
                seen_chunks.add(hit.chunk.chunk_id)
                if len(packets) >= self.max_packets:
                    return tuple(packets)
                break
        return tuple(packets)

    @staticmethod
    def _packet(signal: Signal, hit: SearchHit, query: str) -> EvidencePacket:
        relative_start, excerpt = _minimal_excerpt(hit.chunk.text, query)
        start = hit.chunk.start_offset + relative_start
        end = start + len(excerpt)
        evidence_id = (
            "E-"
            + hashlib.sha256(f"{signal.signal_id}|{hit.chunk.chunk_id}|{start}|{end}".encode())
            .hexdigest()[:12]
            .upper()
        )
        return EvidencePacket(
            evidence_id=evidence_id,
            signal_id=signal.signal_id,
            source=hit.chunk.source,
            section=hit.chunk.section,
            subsection=hit.chunk.subsection,
            chunk_id=hit.chunk.chunk_id,
            start_offset=start,
            end_offset=end,
            excerpt=excerpt,
            relevance_score=max(hit.score, Decimal("0")),
            selection_reason=(
                f"Lexical match for {signal.test_id}; filtered to CIK {hit.chunk.cik} "
                f"and retained section {hit.chunk.section}."
            ),
            parser_version=hit.chunk.parser_version,
            token_count=max(1, len(excerpt.split())),
        )


def resolve_citation(packet: EvidencePacket) -> str:
    source = packet.source
    accession = source.accession_number or "unknown accession"
    return f"[{packet.evidence_id}] {packet.section}, {accession}, {source.source_url}"


def _minimal_excerpt(text: str, query: str, max_chars: int = 700) -> tuple[int, str]:
    terms = [term.casefold() for term in _TERM.findall(query) if len(term) >= 4]
    folded = text.casefold()
    positions = [folded.find(term) for term in terms if folded.find(term) >= 0]
    center = min(positions) if positions else 0
    start = max(0, center - max_chars // 3)
    end = min(len(text), start + max_chars)
    start = _sentence_start(text, start)
    end = _sentence_end(text, end)
    return start, text[start:end].strip()


def _sentence_start(text: str, offset: int) -> int:
    boundary = max(text.rfind(". ", 0, offset), text.rfind("\n", 0, offset))
    return boundary + 2 if boundary >= 0 and text[boundary : boundary + 2] == ". " else boundary + 1


def _sentence_end(text: str, offset: int) -> int:
    boundary = text.find(". ", offset)
    return boundary + 1 if boundary >= 0 else min(len(text), offset)
