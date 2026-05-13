# Load tests

Pre-prod sanity checks for the changes from the May-2026 review pass:

- **P6 동시성** — `portfolio.analyze` and `market_snapshot.fetch_snapshot` were
  refactored to fan out blocking IO via `ThreadPoolExecutor`. These tests
  inject deterministic sleeps into the per-holding / per-fetcher path and
  assert that wall-clock elapsed time is much closer to *one* sleep than to
  the sum of all sleeps.
- **P11 health** — `/api/health` was extended with environment self-diagnosis
  (uptime, groq_configured, cache_writable, cors_origins_count). The test
  fires 200 concurrent requests via the FastAPI TestClient and asserts both
  full success and a sane p95 latency budget.

## Running

```bash
cd backend
python -m pytest tests/loadtest/ -v
```

These run alongside the regular test suite — no external services needed,
no rate-limit concerns, no real Groq / Binance / FDR calls.

For a one-shot performance report (numbers printed to stdout, no assertions):

```bash
python -m tests.loadtest.report
```
