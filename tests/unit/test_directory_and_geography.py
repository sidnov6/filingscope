from __future__ import annotations

from filingscope.geography import geographic_evidence_from_submissions
from filingscope.sec.directory import parse_company_directory


def test_company_directory_parses_and_normalizes_official_shape() -> None:
    entries = parse_company_directory(
        {
            "0": {"cik_str": 320193, "ticker": "aapl", "title": "Apple Inc."},
            "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
        }
    )

    assert entries[0].cik == "0000320193"
    assert entries[0].ticker == "AAPL"
    assert entries[1].legal_name == "Microsoft Corp"


def test_geography_uses_sourced_address_and_discloses_centroid_precision() -> None:
    locations = geographic_evidence_from_submissions(
        {
            "addresses": {
                "business": {
                    "street1": "ONE APPLE PARK WAY",
                    "city": "CUPERTINO",
                    "stateOrCountry": "CA",
                    "zipCode": "95014",
                }
            }
        },
        source_url="https://data.sec.gov/submissions/CIK0000320193.json",
        source_hash="a" * 64,
    )

    assert len(locations) == 1
    assert locations[0].precision == "administrative_area_centroid"
    assert "not evidence of operating" in locations[0].limitation
    assert locations[0].source_sha256 == "a" * 64


def test_geography_does_not_infer_unknown_locations() -> None:
    assert (
        geographic_evidence_from_submissions(
            {"addresses": {"business": {"city": "UNKNOWN"}}},
            source_url="https://data.sec.gov/submissions/CIK0000000001.json",
            source_hash="b" * 64,
        )
        == ()
    )
