"""
Regression test suite for UTC Datetime Modernization (Batch 3).

Verifies:
1. Candidate evidence retrieval endpoint (/api/v1/papers/evidence) returns timezone-aware UTC datetimes.
2. Timestamps parse into datetime objects with tzinfo == timezone.utc or valid UTC offset.
3. No TypeError occurs when comparing returned timestamps against datetime.now(timezone.utc).
4. Serialization into JSON produces valid ISO 8601 strings with explicit UTC indicator.
"""
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_transient_evidence_endpoint_returns_timezone_aware_utc_datetimes():
    """Verify POST /api/v1/papers/evidence produces timezone-aware UTC timestamps."""
    payload = {
        "title": "Quantum Error Correction via Surface Codes",
        "abstract": "We analyze topological surface codes for quantum computation. Empirical results demonstrate a fault-tolerance threshold of 1 percent under depolarizing noise.",
        "raw_text": "We analyze topological surface codes for quantum computation. Empirical results demonstrate a fault-tolerance threshold of 1 percent under depolarizing noise."
    }
    resp = client.post("/api/v1/papers/evidence", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["evidence_count"] >= 1
    for ev in data["evidence"]:
        created_str = ev["created_at"]
        updated_str = ev["updated_at"]
        assert created_str is not None
        assert updated_str is not None

        # Parse ISO string
        created_dt = datetime.fromisoformat(created_str)
        updated_dt = datetime.fromisoformat(updated_str)

        # 1. Verify timezone awareness
        assert created_dt.tzinfo is not None, f"created_at {created_str} is naive, expected timezone-aware"
        assert updated_dt.tzinfo is not None, f"updated_at {updated_str} is naive, expected timezone-aware"

        # 2. Verify comparison with datetime.now(timezone.utc) does NOT raise TypeError
        now_utc = datetime.now(timezone.utc)
        diff_seconds = abs((now_utc - created_dt).total_seconds())
        assert diff_seconds < 60, f"Timestamp is more than 60 seconds off: {diff_seconds}s"

        # 3. Verify ISO string contains timezone indicator (+00:00 or Z)
        assert ("+00:00" in created_str or created_str.endswith("Z"))
        assert ("+00:00" in updated_str or updated_str.endswith("Z"))
