from __future__ import annotations

import json
import os
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, TypeVar, cast

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel

from filingscope.errors import StorageError
from filingscope.schemas import (
    SCHEMA_VERSION,
    AgentOutputRecord,
    AnomalyResult,
    CompanyIdentity,
    DataQualityFinding,
    EvidencePacket,
    FilingChunk,
    FilingMetadata,
    ForensicTestResult,
    InvestigationReport,
    InvestigationRunMetadata,
    MetricResult,
    NormalizedFinancialFact,
    RawXbrlFact,
    Signal,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class ParquetDuckDbStore:
    """Idempotent local persistence with versioned Parquet and DuckDB views."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.warehouse_dir = data_dir / "warehouse"
        self.database_path = data_dir / "filingscope.duckdb"

    def persist_ingestion(
        self,
        company: CompanyIdentity,
        filings: list[FilingMetadata],
        facts: list[RawXbrlFact],
    ) -> None:
        try:
            self._write_records(
                self.warehouse_dir / "companies" / f"version={SCHEMA_VERSION}" / "records.parquet",
                [company],
                key_fields=("cik",),
                dataset="companies",
            )
            partition = f"cik={company.cik}"
            self._write_records(
                self.warehouse_dir
                / "filings"
                / f"version={SCHEMA_VERSION}"
                / partition
                / "records.parquet",
                filings,
                key_fields=("accession_number",),
                dataset="filings",
            )
            self._write_records(
                self.warehouse_dir
                / "raw_xbrl_facts"
                / f"version={SCHEMA_VERSION}"
                / partition
                / "records.parquet",
                facts,
                key_fields=("fact_id",),
                dataset="raw_xbrl_facts",
            )
            self._refresh_duckdb_views()
        except (OSError, ValueError, pa.ArrowException, duckdb.Error) as error:
            raise StorageError(
                message="Local analytical persistence failed",
                code="storage_write_failed",
                details={"reason": str(error)},
            ) from error

    def persist_normalization(
        self,
        *,
        cik: str,
        mapping_version: str,
        facts: list[NormalizedFinancialFact],
        findings: list[DataQualityFinding],
    ) -> None:
        try:
            facts_by_year: dict[str, list[NormalizedFinancialFact]] = {}
            for fact in facts:
                fiscal_year = str(fact.period.fiscal_year or "unknown")
                facts_by_year.setdefault(fiscal_year, []).append(fact)
            for fiscal_year, year_facts in facts_by_year.items():
                self._write_records(
                    self.warehouse_dir
                    / "normalized_facts"
                    / f"version={SCHEMA_VERSION}"
                    / f"mapping={mapping_version}"
                    / f"cik={cik}"
                    / f"fiscal_year={fiscal_year}"
                    / "records.parquet",
                    year_facts,
                    key_fields=("normalized_fact_id",),
                    dataset="normalized_facts",
                )
            self._write_records(
                self.warehouse_dir
                / "data_quality_findings"
                / f"version={SCHEMA_VERSION}"
                / f"mapping={mapping_version}"
                / f"cik={cik}"
                / "records.parquet",
                findings,
                key_fields=("finding_id",),
                dataset="data_quality_findings",
            )
            self._refresh_duckdb_views()
        except (OSError, ValueError, pa.ArrowException, duckdb.Error) as error:
            raise StorageError(
                message="Normalized analytical persistence failed",
                code="normalization_storage_write_failed",
                details={"reason": str(error)},
            ) from error

    def persist_analysis(
        self,
        *,
        cik: str,
        metrics: list[MetricResult],
        tests: list[ForensicTestResult],
        anomalies: list[AnomalyResult],
        signals: list[Signal],
    ) -> None:
        try:
            partition = f"version={SCHEMA_VERSION}/cik={cik}"
            self._write_records(
                self.warehouse_dir / "metric_results" / partition / "records.parquet",
                metrics,
                key_fields=("metric_result_id",),
                dataset="metric_results",
            )
            self._write_records(
                self.warehouse_dir / "test_results" / partition / "records.parquet",
                tests,
                key_fields=("test_result_id",),
                dataset="test_results",
            )
            self._write_records(
                self.warehouse_dir / "anomalies" / partition / "records.parquet",
                anomalies,
                key_fields=("anomaly_id",),
                dataset="anomalies",
            )
            self._write_records(
                self.warehouse_dir / "signals" / partition / "records.parquet",
                signals,
                key_fields=("signal_id",),
                dataset="signals",
            )
            self._refresh_duckdb_views()
        except (OSError, ValueError, pa.ArrowException, duckdb.Error) as error:
            raise StorageError(
                message="Analytical persistence failed",
                code="analysis_storage_write_failed",
                details={"reason": str(error)},
            ) from error

    def persist_filing_chunks(self, *, cik: str, chunks: list[FilingChunk]) -> None:
        try:
            self._write_records(
                self.warehouse_dir
                / "filing_chunks"
                / f"version={SCHEMA_VERSION}"
                / f"cik={cik}"
                / "records.parquet",
                chunks,
                key_fields=("chunk_id",),
                dataset="filing_chunks",
            )
            self._refresh_duckdb_views()
        except (OSError, ValueError, pa.ArrowException, duckdb.Error) as error:
            raise StorageError(
                message="Filing chunk persistence failed",
                code="filing_chunk_storage_failed",
                details={"reason": str(error)},
            ) from error

    def persist_evidence(self, *, cik: str, packets: list[EvidencePacket]) -> None:
        try:
            self._write_records(
                self.warehouse_dir
                / "evidence_packets"
                / f"version={SCHEMA_VERSION}"
                / f"cik={cik}"
                / "records.parquet",
                packets,
                key_fields=("evidence_id",),
                dataset="evidence_packets",
            )
            self._refresh_duckdb_views()
        except (OSError, ValueError, pa.ArrowException, duckdb.Error) as error:
            raise StorageError(
                message="Evidence packet persistence failed",
                code="evidence_storage_failed",
                details={"reason": str(error)},
            ) from error

    def persist_investigation_run(self, run: InvestigationRunMetadata) -> None:
        try:
            self._write_records(
                self.warehouse_dir
                / "investigation_runs"
                / f"version={SCHEMA_VERSION}"
                / f"cik={run.cik}"
                / "records.parquet",
                [run],
                key_fields=("run_id",),
                dataset="investigation_runs",
            )
            self._refresh_duckdb_views()
        except (OSError, ValueError, pa.ArrowException, duckdb.Error) as error:
            raise StorageError(
                message="Investigation run persistence failed",
                code="investigation_storage_failed",
                details={"reason": str(error)},
            ) from error

    def persist_agent_outputs(self, report: InvestigationReport) -> None:
        outputs: list[tuple[str, BaseModel]] = []
        for role, output in (
            ("planner", report.plan),
            ("investigator", report.investigator),
            ("bull", report.bull_case),
            ("skeptical", report.skeptical_case),
            (
                "verifier",
                None if not report.verifications else _verification_model(report),
            ),
            ("judge", report.assessment),
        ):
            if output is not None:
                outputs.append((role, output))
        records = [
            AgentOutputRecord(
                output_id=f"{report.run.run_id}:{role}",
                run_id=report.run.run_id,
                cik=report.company.cik,
                role=role,
                prompt_version=report.run.prompt_version or "not_used",
                model_name=report.run.model_metadata.get("model", "unknown"),
                output_json=output.model_dump_json(),
            )
            for role, output in outputs
        ]
        if not records:
            return
        try:
            self._write_records(
                self.warehouse_dir
                / "agent_outputs"
                / f"version={SCHEMA_VERSION}"
                / f"cik={report.company.cik}"
                / "records.parquet",
                records,
                key_fields=("output_id",),
                dataset="agent_outputs",
            )
            self._refresh_duckdb_views()
        except (OSError, ValueError, pa.ArrowException, duckdb.Error) as error:
            raise StorageError(
                message="Agent output persistence failed",
                code="agent_output_storage_failed",
                details={"reason": str(error)},
            ) from error

    def agent_outputs(self, run_id: str) -> list[AgentOutputRecord]:
        return self._read_models(
            "agent_outputs",
            AgentOutputRecord,
            "run_id = ?",
            [run_id],
            order_by="role, output_id",
        )

    def counts(self) -> dict[str, int]:
        if not self.database_path.exists():
            return {"companies": 0, "filings": 0, "raw_xbrl_facts": 0}
        with duckdb.connect(str(self.database_path), read_only=True) as connection:
            counts: dict[str, int] = {}
            for view in ("companies", "filings", "raw_xbrl_facts"):
                row = connection.execute(f'SELECT count(*) FROM "{view}"').fetchone()
                if row is None:
                    raise StorageError(
                        message=f"DuckDB view {view} returned no count row",
                        code="storage_query_failed",
                    )
                counts[view] = int(row[0])
            return counts

    def normalization_counts(self) -> dict[str, int]:
        if not self.database_path.exists():
            return {"normalized_facts": 0, "data_quality_findings": 0}
        with duckdb.connect(str(self.database_path), read_only=True) as connection:
            counts: dict[str, int] = {}
            for view in ("normalized_facts", "data_quality_findings"):
                exists = connection.execute(
                    "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
                    [view],
                ).fetchone()
                if not exists or int(exists[0]) == 0:
                    counts[view] = 0
                    continue
                row = connection.execute(f'SELECT count(*) FROM "{view}"').fetchone()
                if row is None:
                    raise StorageError(
                        message=f"DuckDB view {view} returned no count row",
                        code="storage_query_failed",
                    )
                counts[view] = int(row[0])
            return counts

    def companies(self) -> list[CompanyIdentity]:
        return self._read_models("companies", CompanyIdentity)

    def company(self, cik: str) -> CompanyIdentity | None:
        rows = self._read_models("companies", CompanyIdentity, "cik = ?", [cik])
        return rows[0] if rows else None

    def filings(self, cik: str) -> list[FilingMetadata]:
        return self._read_models(
            "filings",
            FilingMetadata,
            "cik = ?",
            [cik],
            order_by="filing_date DESC, accession_number DESC",
        )

    def normalized_facts(self, cik: str) -> list[NormalizedFinancialFact]:
        return self._read_models(
            "normalized_facts",
            NormalizedFinancialFact,
            "cik = ?",
            [cik],
            order_by=(
                "canonical_metric, period.end_date, "
                "coalesce(period.start_date, period.end_date), accession_number"
            ),
        )

    def data_quality_findings(self, cik: str) -> list[DataQualityFinding]:
        return self._read_models(
            "data_quality_findings",
            DataQualityFinding,
            "cik = ?",
            [cik],
            order_by="severity DESC, category, finding_id",
        )

    def metric_results(self, cik: str) -> list[MetricResult]:
        return self._read_models(
            "metric_results",
            MetricResult,
            "cik = ?",
            [cik],
            order_by="metric_id, period.end_date, metric_result_id",
        )

    def test_results(self, cik: str) -> list[ForensicTestResult]:
        return self._read_models(
            "test_results",
            ForensicTestResult,
            "cik = ?",
            [cik],
            order_by="test_id, period.end_date, test_result_id",
        )

    def anomalies(self, cik: str) -> list[AnomalyResult]:
        return self._read_models(
            "anomalies",
            AnomalyResult,
            "cik = ?",
            [cik],
            order_by="metric_id, period.end_date, anomaly_id",
        )

    def signals(self, cik: str) -> list[Signal]:
        return self._read_models(
            "signals",
            Signal,
            "cik = ?",
            [cik],
            order_by="score DESC, signal_id",
        )

    def filing_chunks(self, cik: str) -> list[FilingChunk]:
        return self._read_models(
            "filing_chunks",
            FilingChunk,
            "cik = ?",
            [cik],
            order_by="accession_number, section, sequence, chunk_id",
        )

    def evidence_packets(self, cik: str) -> list[EvidencePacket]:
        return self._read_models(
            "evidence_packets",
            EvidencePacket,
            "cik = ?",
            [cik],
            order_by="evidence_id",
        )

    def evidence_packet(self, evidence_id: str) -> EvidencePacket | None:
        rows = self._read_models(
            "evidence_packets",
            EvidencePacket,
            "evidence_id = ?",
            [evidence_id],
        )
        return rows[0] if rows else None

    def investigation_runs(self, cik: str | None = None) -> list[InvestigationRunMetadata]:
        return self._read_models(
            "investigation_runs",
            InvestigationRunMetadata,
            "cik = ?" if cik else None,
            [cik] if cik else None,
            order_by="started_at DESC, run_id",
        )

    def _read_models(
        self,
        view: str,
        model: type[ModelT],
        where: str | None = None,
        parameters: list[object] | None = None,
        *,
        order_by: str | None = None,
    ) -> list[ModelT]:
        if not self.database_path.exists():
            return []
        fields = list(model.model_fields)
        projection = ", ".join(f'"{field}"' for field in fields)
        query = f'SELECT {projection} FROM "{view}"'
        if where:
            query += f" WHERE {where}"
        if order_by:
            query += f" ORDER BY {order_by}"
        try:
            with duckdb.connect(str(self.database_path), read_only=True) as connection:
                exists = connection.execute(
                    "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
                    [view],
                ).fetchone()
                if not exists or int(exists[0]) == 0:
                    return []
                cursor = connection.execute(query, parameters or [])
                names = [description[0] for description in cursor.description]
                return [
                    model.model_validate(dict(zip(names, row, strict=True)))
                    for row in cursor.fetchall()
                ]
        except (duckdb.Error, ValueError) as error:
            raise StorageError(
                message=f"Could not query DuckDB view {view}",
                code="storage_query_failed",
                details={"reason": str(error)},
            ) from error

    def _write_records(
        self,
        path: Path,
        records: Iterable[BaseModel],
        *,
        key_fields: Sequence[str],
        dataset: str,
    ) -> bool:
        incoming = [_json_record(record) for record in records]
        existing = self._read_records(path) if path.exists() else []
        merged = {_record_key(record, key_fields): record for record in existing}
        merged.update({_record_key(record, key_fields): record for record in incoming})
        ordered = [merged[key] for key in sorted(merged)]
        existing_ordered = sorted(existing, key=lambda record: _record_key(record, key_fields))
        if existing_ordered == ordered:
            return False
        if not ordered:
            return False

        path.parent.mkdir(parents=True, exist_ok=True)
        table = pa.Table.from_pylist(ordered).replace_schema_metadata(
            {
                b"filingscope.schema_version": SCHEMA_VERSION.encode(),
                b"filingscope.dataset": dataset.encode(),
            }
        )
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        pq.write_table(
            table,
            temporary,
            compression="zstd",
            use_dictionary=True,
            write_statistics=True,
        )
        os.replace(temporary, path)
        return True

    @staticmethod
    def _read_records(path: Path) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], pq.ParquetFile(path).read().to_pylist())

    def _refresh_duckdb_views(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with duckdb.connect(str(self.database_path)) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_versions (
                    dataset VARCHAR PRIMARY KEY,
                    schema_version VARCHAR NOT NULL
                )
                """
            )
            for dataset in (
                "companies",
                "filings",
                "raw_xbrl_facts",
                "normalized_facts",
                "data_quality_findings",
                "metric_results",
                "test_results",
                "anomalies",
                "signals",
                "filing_chunks",
                "evidence_packets",
                "investigation_runs",
                "agent_outputs",
            ):
                dataset_dir = self.warehouse_dir / dataset
                if not any(dataset_dir.rglob("*.parquet")):
                    continue
                glob = (dataset_dir / "version=*" / "**" / "*.parquet").as_posix()
                escaped_glob = glob.replace("'", "''")
                connection.execute(
                    f"CREATE OR REPLACE VIEW {dataset} AS "
                    f"SELECT * FROM read_parquet("
                    f"'{escaped_glob}', hive_partitioning = true, union_by_name = true)"
                )
                connection.execute(
                    "INSERT OR REPLACE INTO schema_versions VALUES (?, ?)",
                    [dataset, SCHEMA_VERSION],
                )


def _json_record(record: BaseModel) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(record.model_dump_json()))


def _record_key(record: dict[str, Any], key_fields: Sequence[str]) -> tuple[str, ...]:
    return tuple(str(record[field]) for field in key_fields)


def _verification_model(report: InvestigationReport) -> BaseModel:
    from filingscope.schemas import VerificationBatch

    return VerificationBatch(verifications=report.verifications)
