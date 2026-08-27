"""Transparent lexical retrieval and citation-ready evidence packets."""

from filingscope.retrieval.evidence import EvidenceBuilder, resolve_citation
from filingscope.retrieval.index import FilingSearchIndex, SearchHit

__all__ = ["EvidenceBuilder", "FilingSearchIndex", "SearchHit", "resolve_citation"]
