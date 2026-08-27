from __future__ import annotations

import hashlib
from typing import Any

from filingscope.schemas import GeographicEvidence

# Approximate administrative-area centroids for orientation only. They are never
# presented as office coordinates or as evidence of geographic business exposure.
US_STATE_CENTROIDS: dict[str, tuple[float, float]] = {
    "AL": (32.8067, -86.7911),
    "AK": (61.3707, -152.4044),
    "AZ": (33.7298, -111.4312),
    "AR": (34.9697, -92.3731),
    "CA": (36.1162, -119.6816),
    "CO": (39.0598, -105.3111),
    "CT": (41.5978, -72.7554),
    "DE": (39.3185, -75.5071),
    "DC": (38.9072, -77.0369),
    "FL": (27.7663, -81.6868),
    "GA": (33.0406, -83.6431),
    "HI": (21.0943, -157.4983),
    "ID": (44.2405, -114.4788),
    "IL": (40.3495, -88.9861),
    "IN": (39.8494, -86.2583),
    "IA": (42.0115, -93.2105),
    "KS": (38.5266, -96.7265),
    "KY": (37.6681, -84.6701),
    "LA": (31.1695, -91.8678),
    "ME": (44.6939, -69.3819),
    "MD": (39.0639, -76.8021),
    "MA": (42.2302, -71.5301),
    "MI": (43.3266, -84.5361),
    "MN": (45.6945, -93.9002),
    "MS": (32.7416, -89.6787),
    "MO": (38.4561, -92.2884),
    "MT": (46.9219, -110.4544),
    "NE": (41.1254, -98.2681),
    "NV": (38.3135, -117.0554),
    "NH": (43.4525, -71.5639),
    "NJ": (40.2989, -74.5210),
    "NM": (34.8405, -106.2485),
    "NY": (42.1657, -74.9481),
    "NC": (35.6301, -79.8064),
    "ND": (47.5289, -99.7840),
    "OH": (40.3888, -82.7649),
    "OK": (35.5653, -96.9289),
    "OR": (44.5720, -122.0709),
    "PA": (40.5908, -77.2098),
    "RI": (41.6809, -71.5118),
    "SC": (33.8569, -80.9450),
    "SD": (44.2998, -99.4388),
    "TN": (35.7478, -86.6923),
    "TX": (31.0545, -97.5635),
    "UT": (40.1500, -111.8624),
    "VT": (44.0459, -72.7107),
    "VA": (37.7693, -78.1700),
    "WA": (47.4009, -121.4905),
    "WV": (38.4912, -80.9545),
    "WI": (44.2685, -89.6165),
    "WY": (42.7560, -107.3025),
}


def geographic_evidence_from_submissions(
    payload: Any,
    *,
    source_url: str,
    source_hash: str,
) -> tuple[GeographicEvidence, ...]:
    if not isinstance(payload, dict):
        return ()
    addresses = payload.get("addresses")
    if not isinstance(addresses, dict):
        return ()
    business = addresses.get("business")
    if not isinstance(business, dict):
        return ()
    state = str(business.get("stateOrCountry") or "").upper()
    coordinates = US_STATE_CENTROIDS.get(state)
    if coordinates is None:
        return ()
    city = str(business.get("city") or "").strip()
    lines = [
        str(business.get(key) or "").strip()
        for key in ("street1", "street2", "city", "stateOrCountry", "zipCode")
    ]
    address = ", ".join(line for line in lines if line)
    evidence_id = hashlib.sha256(f"{source_hash}|business|{address}".encode()).hexdigest()
    return (
        GeographicEvidence(
            geographic_evidence_id=evidence_id,
            label=f"Registered business address · {city or state}",
            latitude=coordinates[0],
            longitude=coordinates[1],
            precision="administrative_area_centroid",
            context="registered_business_address",
            address=address,
            source_url=source_url,
            source_sha256=source_hash,
            limitation=(
                "Marker is the state centroid for orientation, not the office coordinate and "
                "not evidence of operating or revenue exposure."
            ),
        ),
    )
