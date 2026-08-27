from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from typing import ClassVar

from filingscope.errors import FilingParseError
from filingscope.schemas import FilingChunk, FilingMetadata, SourceReference

PARSER_VERSION = "1.0.0"
_ITEM_HEADING = re.compile(r"(?im)^(?:(PART\s+[IVX]+)\s+)?ITEM\s+([0-9]+[A-Z]?)(?:\.|\s|$)\s*(.*)$")
_SPACE = re.compile(r"[ \t\f\v]+")
_BLANKS = re.compile(r"\n{3,}")


class _TextExtractor(HTMLParser):
    _ignored: ClassVar[frozenset[str]] = frozenset({"script", "style", "nav", "noscript", "svg"})
    _blocks: ClassVar[frozenset[str]] = frozenset(
        {
            "address",
            "article",
            "aside",
            "blockquote",
            "br",
            "div",
            "footer",
            "h1",
            "h2",
            "h3",
            "h4",
            "header",
            "li",
            "p",
            "section",
            "table",
            "td",
            "th",
            "tr",
        }
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in self._ignored:
            self.ignored_depth += 1
        elif tag in self._blocks and not self.ignored_depth:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._ignored:
            self.ignored_depth = max(0, self.ignored_depth - 1)
        elif tag in self._blocks and not self.ignored_depth:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.parts.append(data)


class FilingDocumentParser:
    def __init__(
        self, *, max_document_bytes: int = 25_000_000, max_chunk_chars: int = 2_400
    ) -> None:
        self.max_document_bytes = max_document_bytes
        self.max_chunk_chars = max_chunk_chars

    def parse(
        self,
        payload: bytes,
        filing: FilingMetadata,
        source: SourceReference,
        *,
        ticker: str | None = None,
    ) -> tuple[FilingChunk, ...]:
        if len(payload) > self.max_document_bytes:
            raise FilingParseError(
                message="Filing document exceeds configured parser size limit",
                code="filing_too_large",
                details={"bytes": len(payload), "limit": self.max_document_bytes},
            )
        try:
            html = payload.decode("utf-8")
        except UnicodeDecodeError:
            html = payload.decode("latin-1")
        extractor = _TextExtractor()
        try:
            extractor.feed(html)
            extractor.close()
        except Exception as error:
            raise FilingParseError(
                message="Filing HTML could not be parsed",
                code="filing_html_invalid",
                details={"accession": filing.accession_number},
            ) from error
        text = _clean_text("".join(extractor.parts))
        if not text:
            raise FilingParseError(
                message="Filing parser produced no readable text",
                code="filing_text_empty",
                details={"accession": filing.accession_number},
            )
        sections = _sections(text)
        chunks: list[FilingChunk] = []
        for section, subsection, section_start, section_text in sections:
            for sequence, (relative_start, chunk_text) in enumerate(
                _chunk_text(section_text, self.max_chunk_chars)
            ):
                start = section_start + relative_start
                end = start + len(chunk_text)
                chunk_id = _stable_id(
                    source.content_sha256,
                    PARSER_VERSION,
                    filing.accession_number,
                    section,
                    str(sequence),
                    chunk_text,
                )
                chunks.append(
                    FilingChunk(
                        chunk_id=chunk_id,
                        cik=filing.cik,
                        ticker=ticker,
                        accession_number=filing.accession_number,
                        form=filing.form,
                        filing_date=filing.filing_date,
                        report_period=filing.report_period,
                        section=section,
                        subsection=subsection,
                        sequence=sequence,
                        text=chunk_text,
                        start_offset=start,
                        end_offset=end,
                        source_url=source.source_url,
                        parser_version=PARSER_VERSION,
                        content_sha256=source.content_sha256,
                        source=source,
                    )
                )
        return tuple(chunks)


def _clean_text(text: str) -> str:
    lines = [_SPACE.sub(" ", line).strip() for line in text.replace("\r", "\n").splitlines()]
    return _BLANKS.sub("\n\n", "\n".join(line for line in lines if line)).strip()


def _sections(text: str) -> list[tuple[str, str | None, int, str]]:
    matches = list(_ITEM_HEADING.finditer(text))
    if not matches:
        return [("Document", None, 0, text)]
    sections: list[tuple[str, str | None, int, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        part = match.group(1)
        item = match.group(2)
        title = match.group(3).strip(" .—-\t") or None
        section = f"{part + ' ' if part else ''}Item {item}"
        sections.append((section, title, start, text[start:end].strip()))
    return sections


def _chunk_text(text: str, max_chars: int) -> list[tuple[int, str]]:
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    chunks: list[tuple[int, str]] = []
    cursor = 0
    current = ""
    current_start = 0
    for paragraph in paragraphs:
        paragraph_start = text.find(paragraph, cursor)
        cursor = paragraph_start + len(paragraph)
        if current and len(current) + 2 + len(paragraph) > max_chars:
            chunks.append((current_start, current))
            current = ""
        if not current:
            current_start = paragraph_start
            current = paragraph
        else:
            current += "\n\n" + paragraph
    if current:
        chunks.append((current_start, current))
    return chunks


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()
