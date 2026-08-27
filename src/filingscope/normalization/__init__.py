"""Canonical fact mappings, period classification, and deterministic selection."""

from filingscope.normalization.engine import NormalizationResult, Normalizer
from filingscope.normalization.mappings import MAPPING_VERSION, MappingRegistry
from filingscope.normalization.periods import PeriodFilter, classify_period, select_periods
from filingscope.normalization.quality import score_data_quality
from filingscope.normalization.selection import SelectionPolicy

__all__ = [
    "MAPPING_VERSION",
    "MappingRegistry",
    "NormalizationResult",
    "Normalizer",
    "PeriodFilter",
    "SelectionPolicy",
    "classify_period",
    "score_data_quality",
    "select_periods",
]
