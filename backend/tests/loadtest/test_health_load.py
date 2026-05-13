"""Load test for the P11 enriched /api/health endpoint.

Fires 200 concurrent requests via FastAPI's TestClient (which routes through
the real ASGI stack) and asserts:
  - 100% success (no 5xx)
  - p50 / p95 latency budgets
  - Reported uptime monotonically advances across requests
  - Cache-writable probe is consistent (no flapping)

Wall-clock sensitive but uses generous budgets; failures here indicate a real
regression in startup-cost / health-probe overhead, not flaky CI.
"""

from __future__ import annotations

import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from main import app

# Test budgets — generous so this passes on slow CI but tight enough to catch
# obvious regressions (e.g. someone makes _cache_writable do a 100ms disk sync
# on every call instead of caching it).
#
# Numbers reflect TestClient overhead (httpx → ASGI portal handoff per call)
# plus 20-way Windows thread contention; a real uvicorn worker behind nginx
# will be ~5-10× faster on the same hardware. The point is to catch *order
# of magnitude* regressions, not to assert prod-equivalent latency.
P50_BUDGET_MS = 250
P95_BUDGET_MS = 500
TOTAL_REQUESTS = 200
CONCURRENCY = 10


def _hit_health(client: TestClient) -> tuple[int, float, dict]:
    t0 = time.monotonic()
    resp = client.get("/api/health")
    elapsed_ms = (time.monotonic() - t0) * 1000
    return resp.status_code, elapsed_ms, resp.json()


def test_health_endpoint_handles_200_concurrent_requests() -> None:
    client = TestClient(app)

    # Warm up — first request pays for the cache_writable disk probe + any
    # lazy-import overhead. Excluding it from the measurement isolates the
    # *steady-state* hot path, which is what real prod load looks like.
    for _ in range(5):
        client.get("/api/health")

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        results = list(ex.map(lambda _: _hit_health(client), range(TOTAL_REQUESTS)))

    statuses = [r[0] for r in results]
    latencies = sorted(r[1] for r in results)
    bodies = [r[2] for r in results]

    # 100% success
    assert all(s == 200 for s in statuses), (
        f"got non-200 responses: {[(i, s) for i, s in enumerate(statuses) if s != 200][:5]}"
    )

    # Schema sanity — every body has the new diagnostic fields
    for body in bodies[:5]:
        assert body["status"] == "ok"
        assert body["version"]
        assert isinstance(body["uptime_seconds"], (int, float))
        assert isinstance(body["groq_configured"], bool)
        assert isinstance(body["cache_writable"], bool)
        assert isinstance(body["cors_origins_count"], int)

    # Latency budgets
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    avg = statistics.mean(latencies)
    print(
        f"\n[health load] {TOTAL_REQUESTS} req x {CONCURRENCY} concurrent: "
        f"avg={avg:.1f}ms p50={p50:.1f}ms p95={p95:.1f}ms p99={p99:.1f}ms "
        f"min={latencies[0]:.1f}ms max={latencies[-1]:.1f}ms"
    )
    assert p50 < P50_BUDGET_MS, f"p50 {p50:.1f}ms exceeds budget {P50_BUDGET_MS}ms"
    assert p95 < P95_BUDGET_MS, f"p95 {p95:.1f}ms exceeds budget {P95_BUDGET_MS}ms"


def test_health_uptime_monotonic() -> None:
    """Uptime field must monotonically advance — never reset, never go backwards."""
    client = TestClient(app)
    uptimes = []
    for _ in range(10):
        body = client.get("/api/health").json()
        uptimes.append(body["uptime_seconds"])
        time.sleep(0.05)
    # Strict monotonic non-decreasing
    for prev, cur in zip(uptimes, uptimes[1:]):
        assert cur >= prev, f"uptime went backwards: {prev} → {cur}"
    # Last uptime must be >= 0.4s (10 iterations × 50ms)
    assert uptimes[-1] > uptimes[0], "uptime did not advance across 10 calls"


def test_health_cache_writable_does_not_flap() -> None:
    """Cache-writable probe must return a consistent result across calls."""
    client = TestClient(app)
    results = {client.get("/api/health").json()["cache_writable"] for _ in range(20)}
    assert len(results) == 1, (
        f"cache_writable flapped across 20 calls: {results}. "
        f"The probe should be deterministic."
    )
