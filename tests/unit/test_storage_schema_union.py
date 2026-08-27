from __future__ import annotations

from datetime import date
from decimal import Decimal

from filingscope.schemas import ComputationStatus, FinancialPeriod, ForensicTestResult
from filingscope.storage import ParquetDuckDbStore


def test_duckdb_views_union_nullable_parquet_schemas_across_companies(tmp_path) -> None:
    store = ParquetDuckDbStore(tmp_path)
    period = FinancialPeriod(period_type="instant", end_date=date(2026, 6, 30))
    missing = ForensicTestResult(
        test_result_id="missing-result-0001",
        test_id="quality_test",
        test_version="1.0.0",
        period=period,
        status=ComputationStatus.NOT_COMPUTABLE,
        result=None,
        threshold_context={"threshold": "not_available"},
        reason="Required inputs are unavailable.",
    )
    computed = ForensicTestResult(
        test_result_id="computed-result-001",
        test_id="quality_test",
        test_version="1.0.0",
        period=period,
        status=ComputationStatus.COMPUTED,
        result=Decimal("1.25"),
        threshold_context={"threshold": "1.0"},
        reason="Computed from available inputs.",
    )

    for cik, record in (("0000320193", missing), ("0001318605", computed)):
        store._write_records(
            store.warehouse_dir
            / "test_results"
            / "version=1.0.0"
            / f"cik={cik}"
            / "records.parquet",
            [record],
            key_fields=("test_result_id",),
            dataset="test_results",
        )
    store._refresh_duckdb_views()

    assert store.test_results("0000320193")[0].result is None
    assert store.test_results("0001318605")[0].result == "1.25"
