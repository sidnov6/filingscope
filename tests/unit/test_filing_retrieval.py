from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from filingscope.filings import FilingDocumentParser
from filingscope.retrieval import EvidenceBuilder, FilingSearchIndex, resolve_citation
from filingscope.schemas import (
    FilingMetadata,
    Signal,
    SignalSeverity,
    SourceReference,
)


def _filing_and_source(payload: bytes) -> tuple[FilingMetadata, SourceReference]:
    content_hash = hashlib.sha256(payload).hexdigest()
    source = SourceReference(
        source_type="sec_filing",
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/320193/000032019318000145/a10-k20189292018.htm"
        ),
        content_sha256=content_hash,
        manifest_id="manifest-filing-2018",
        retrieved_at=datetime(2026, 8, 27, tzinfo=UTC),
        accession_number="0000320193-18-000145",
    )
    filing = FilingMetadata(
        accession_number="0000320193-18-000145",
        cik="0000320193",
        form="10-K",
        filing_date=date(2018, 11, 5),
        report_period=date(2018, 9, 29),
        primary_document="a10-k20189292018.htm",
        source=source,
    )
    return filing, source


def test_section_parser_has_stable_chunks_and_ignores_active_content(
    fixture_dir: Path,
) -> None:
    payload = (fixture_dir / "aapl_2018_10k_excerpt.html").read_bytes()
    filing, source = _filing_and_source(payload)
    parser = FilingDocumentParser(max_chunk_chars=300)

    first = parser.parse(payload, filing, source, ticker="AAPL")
    second = parser.parse(payload, filing, source, ticker="AAPL")

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert {chunk.section for chunk in first} == {"Item 7", "Item 8", "Item 9A"}
    assert all("override evidence rules" not in chunk.text for chunk in first)
    assert all(chunk.end_offset > chunk.start_offset for chunk in first)


def test_fts_retrieval_and_evidence_packet_are_citation_ready(
    tmp_path: Path,
    fixture_dir: Path,
) -> None:
    payload = (fixture_dir / "aapl_2018_10k_excerpt.html").read_bytes()
    filing, source = _filing_and_source(payload)
    chunks = FilingDocumentParser(max_chunk_chars=300).parse(payload, filing, source, ticker="AAPL")
    index = FilingSearchIndex(tmp_path / "filing-search.sqlite3")
    index.index(chunks)

    hits = index.search("internal control effective", cik="0000320193", limit=3)
    assert hits
    assert hits[0].chunk.section == "Item 9A"

    signal = Signal(
        signal_id="signal-controls-001",
        category="controls",
        test_id="internal_control_review",
        severity=SignalSeverity.MODERATE,
        materiality=None,
        persistence="unknown",
        data_confidence=Decimal("1"),
        evidence_requirements=("Item 9A internal control effective",),
        score=Decimal("0.5"),
        score_explanation="Fixture screening signal for retrieval evaluation.",
        source_test_result_ids=("test-controls-001",),
    )
    packets = EvidenceBuilder(index).for_signals("0000320193", [signal])

    assert len(packets) == 1
    assert packets[0].evidence_id.startswith("E-")
    assert packets[0].section == "Item 9A"
    assert packets[0].source.content_sha256 == hashlib.sha256(payload).hexdigest()
    assert "0000320193-18-000145" in resolve_citation(packets[0])


def test_labeled_retrieval_recall_and_mrr_are_one(
    tmp_path: Path,
    fixture_dir: Path,
) -> None:
    payload = (fixture_dir / "aapl_2018_10k_excerpt.html").read_bytes()
    filing, source = _filing_and_source(payload)
    chunks = FilingDocumentParser().parse(payload, filing, source)
    index = FilingSearchIndex(tmp_path / "evaluation.sqlite3")
    index.index(chunks)
    labels = [
        ("research development products", "Item 7"),
        ("net sales 265.595", "Item 8"),
        ("internal control effective", "Item 9A"),
    ]
    reciprocal_ranks: list[Decimal] = []
    recalled = 0
    for query, expected_section in labels:
        hits = index.search(query, cik="0000320193", limit=3)
        rank = next(
            (index + 1 for index, hit in enumerate(hits) if hit.chunk.section == expected_section),
            None,
        )
        if rank is not None:
            recalled += 1
            reciprocal_ranks.append(Decimal("1") / Decimal(rank))

    recall_at_3 = Decimal(recalled) / Decimal(len(labels))
    mean_reciprocal_rank = sum(reciprocal_ranks, Decimal("0")) / Decimal(len(labels))
    assert recall_at_3 == Decimal("1")
    assert mean_reciprocal_rank == Decimal("1")
