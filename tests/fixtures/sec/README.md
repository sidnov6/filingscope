# Recorded SEC fixtures

These files are schema-preserving excerpts captured from the SEC's public JSON endpoints on
2026-08-27. They are committed so the test suite never requires live SEC access.

- `aapl_submissions_excerpt.json` originates from
  `https://data.sec.gov/submissions/CIK0000320193.json`. It retains four recent Apple 10-Q/8-K
  records, the entity identity fields used by the ingestion contract, and the registered business
  and mailing address used only for the provenance-labelled geography view.
- `aapl_companyfacts_excerpt.json` originates from
  `https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json`. It retains six reported facts
  across Assets, Revenues, and NetIncomeLoss. Descriptions were shortened only to avoid carrying
  unused prose; fact values, periods, accessions, forms, filing dates, units, and frames are
  unchanged.

The fixture bytes are treated as immutable raw responses by offline tests. These excerpts are not
a canonical normalization mapping and must not be used as analytical or investment conclusions.

`aapl_normalized_expected.json` is a reviewed golden projection produced from those immutable raw
facts under mapping version `1.0.0`. It records only the canonical metric, value, unit, period,
reporting basis, form, and accession needed to detect normalization regressions; provenance and
selection rationale are asserted separately in the tests.

`aapl_2018_10k_excerpt.html` is a deliberately small, sanitized HTML excerpt keyed to Apple’s
[2018 Form 10-K](https://www.sec.gov/Archives/edgar/data/320193/000032019318000145/a10-k20189292018.htm),
filed 2018-11-05. It preserves three Item boundaries, one reported net-sales value, and a short
controls statement needed for parser and lexical-retrieval evaluation. Navigation and active HTML
content are test controls rather than filing evidence. It is not a substitute for the full filing.
