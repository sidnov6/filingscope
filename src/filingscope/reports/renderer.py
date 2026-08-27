from __future__ import annotations

import json
import os
from pathlib import Path

from filingscope.retrieval import resolve_citation
from filingscope.schemas import AgentCase, InvestigationReport


class ReportRenderer:
    def render_json(self, report: InvestigationReport) -> str:
        return report.model_dump_json(indent=2)

    def render_markdown(self, report: InvestigationReport) -> str:
        lines = [
            f"# FilingScope accounting-quality review — {report.company.legal_name}",
            "",
            f"Run `{report.run.run_id}` · status `{report.run.status}` · "
            f"CIK `{report.company.cik}`",
            "",
            "> Screening research only. This report does not establish fraud, provide investment "
            "advice, or replace professional accounting, audit, legal, or investment judgment.",
            "",
            "## Deterministic results",
            "",
            f"- Normalized/derived metric results: {len(report.metrics)}",
            f"- Versioned forensic tests: {len(report.tests)}",
            f"- Ranked screening signals: {len(report.signals)}",
            f"- Data-quality findings: {len(report.findings)}",
            "",
        ]
        if report.signals:
            lines.extend(["### Ranked signals", ""])
            for signal in report.signals:
                lines.append(
                    f"- `{signal.test_id}` — {signal.severity}; score {signal.score}. "
                    f"{signal.score_explanation}"
                )
            lines.append("")
        else:
            lines.extend(
                [
                    "No signal met the configured deterministic screening policy. This does not "
                    "establish that accounting risk is absent.",
                    "",
                ]
            )
        lines.extend(["## Evidence", ""])
        if report.evidence:
            for packet in report.evidence:
                lines.extend(
                    [
                        f"### {packet.evidence_id} — {packet.section}",
                        "",
                        packet.excerpt,
                        "",
                        resolve_citation(packet),
                        "",
                    ]
                )
        else:
            lines.extend(["No evidence packets were selected for this run.", ""])
        lines.extend(self._case_section("Investigator", report.investigator))
        lines.extend(self._case_section("Bull case", report.bull_case))
        lines.extend(self._case_section("Skeptical case", report.skeptical_case))
        lines.extend(["## Assessment", ""])
        if report.assessment:
            lines.extend(
                [
                    report.assessment.summary,
                    "",
                    f"Confidence: {report.assessment.confidence}",
                    "",
                    report.assessment.risk_language_disclosure,
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "Agent assessment is pending or was not required. Deterministic results remain "
                    "available and no narrative conclusion was fabricated.",
                    "",
                ]
            )
        lines.extend(["## Limitations and audit", ""])
        limitations = (
            report.assessment.limitations
            if report.assessment
            else (
                "Recorded fixture coverage may be incomplete.",
                "Missing inputs remain not computable rather than zero-filled.",
                "A lack of ranked signals is not evidence of absence of accounting risk.",
            )
        )
        lines.extend(f"- {item}" for item in limitations)
        lines.extend(
            [
                "",
                f"- Mapping version: `{report.run.mapping_version or 'not recorded'}`",
                f"- Prompt version: `{report.run.prompt_version or 'not used'}`",
                f"- Configuration hash: `{report.run.configuration_hash}`",
                f"- Source manifests: {', '.join(report.run.source_manifest_ids) or 'none'}",
                "",
            ]
        )
        return "\n".join(lines)

    def audit_manifest(self, report: InvestigationReport) -> dict[str, object]:
        return {
            "run": report.run.model_dump(mode="json"),
            "source_chain": {
                "normalized_fact_ids": sorted(
                    {fact_id for metric in report.metrics for fact_id in metric.input_fact_ids}
                ),
                "metric_result_ids": [metric.metric_result_id for metric in report.metrics],
                "test_result_ids": [test.test_result_id for test in report.tests],
                "signal_ids": [signal.signal_id for signal in report.signals],
                "evidence": [
                    {
                        "evidence_id": packet.evidence_id,
                        "chunk_id": packet.chunk_id,
                        "source_hash": packet.source.content_sha256,
                        "source_url": str(packet.source.source_url),
                    }
                    for packet in report.evidence
                ],
                "verified_claim_ids": [item.claim_id for item in report.verifications],
            },
        }

    def write(self, report: InvestigationReport, output_dir: Path) -> dict[str, Path]:
        run_dir = output_dir / report.run.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "json": run_dir / "report.json",
            "markdown": run_dir / "report.md",
            "audit": run_dir / "audit.json",
        }
        self._atomic_write(paths["json"], self.render_json(report))
        self._atomic_write(paths["markdown"], self.render_markdown(report))
        self._atomic_write(
            paths["audit"],
            json.dumps(self.audit_manifest(report), indent=2, sort_keys=True),
        )
        return paths

    @staticmethod
    def read(path: Path) -> InvestigationReport:
        return InvestigationReport.model_validate_json(path.read_text())

    @staticmethod
    def _case_section(title: str, case: AgentCase | None) -> list[str]:
        lines = [f"## {title}", ""]
        if case is None:
            return [*lines, "Not available for this run.", ""]
        for claim in case.claims:
            references = [
                *claim.evidence_ids,
                *claim.fact_ids,
                *claim.metric_result_ids,
            ]
            lines.append(
                f"- {claim.text} References: {', '.join(references)}. "
                f"Confidence: {claim.confidence}."
            )
        if case.evidence_gaps:
            lines.append("- Evidence gaps: " + "; ".join(case.evidence_gaps))
        lines.append("")
        return lines

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(content)
        os.replace(temporary, path)
