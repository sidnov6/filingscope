from __future__ import annotations

from dataclasses import dataclass

from filingscope.filings import FilingDocumentParser
from filingscope.schemas import FilingChunk, FilingMetadata, SourceReference
from filingscope.sec.client import FetchResult, SecHttpClient


@dataclass(frozen=True, slots=True)
class FilingIngestionResult:
    filing: FilingMetadata
    chunks: tuple[FilingChunk, ...]
    source: SourceReference
    from_cache: bool


class SecFilingService:
    def __init__(self, client: SecHttpClient, parser: FilingDocumentParser | None = None) -> None:
        self.client = client
        self.parser = parser or FilingDocumentParser()

    def ingest(self, filing: FilingMetadata, *, ticker: str | None = None) -> FilingIngestionResult:
        url = filing_document_url(filing)
        fetch = self.client.fetch(
            url,
            namespace="filings",
            identity=f"{filing.cik}/{filing.accession_number}",
            accession_number=filing.accession_number,
        )
        source = _source(fetch, filing.accession_number)
        chunks = self.parser.parse(fetch.payload, filing, source, ticker=ticker)
        return FilingIngestionResult(filing, chunks, source, fetch.from_cache)


def filing_document_url(filing: FilingMetadata) -> str:
    accession_compact = filing.accession_number.replace("-", "")
    cik_compact = str(int(filing.cik))
    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{cik_compact}/{accession_compact}/{filing.primary_document}"
    )


def _source(fetch: FetchResult, accession_number: str) -> SourceReference:
    return SourceReference(
        source_type="sec_filing",
        source_url=fetch.manifest.canonical_url,
        content_sha256=fetch.manifest.content_sha256,
        manifest_id=fetch.manifest.manifest_id,
        retrieved_at=fetch.manifest.retrieved_at,
        accession_number=accession_number,
    )
