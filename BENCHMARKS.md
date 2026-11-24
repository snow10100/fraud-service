# Benchmarks

## Docker images

| Image | Size on disk | Compressed | Build time (cold) | Rebuild (no change) | User |
|---|---|---|---|---|---|
| naive (`python:3.12`) | 3.12GB | 792MB | 2m54s | 3s | root |
| dev (multi-stage, `python:3.12-slim`) | 847MB | 180MB | 1m20s | 2s (code-only change) | appuser |

## Container (compose, `--workers 2`, 512MB limit)

Load test: `python scripts/loadtest.py` (2000 requests, 25 concurrent clients)

| p50 | p99 | max | Throughput | Non-2xx |
|---|---|---|---|---|
| 49.7 ms | 96.4 ms | 118.2 ms | 486 req/s | 0 |

| Memory (fraud-api) | Graceful stop |
|---|---|
| 306.5MiB / 512MiB (60%) | 1.1s |

## Test suite

| Level | Tests | Time |
|---|---|---|
| Unit (`-m unit`) | 16 | 0.01s |
| Integration (`-m integration`) | 46 | 0.87s |
| Behavioural, fast | 5 | 0.50s |
| Behavioural, golden file (`-m slow`) | 1 | 9.0s |
| **Per-commit gate (`-m "not slow"`)** | **67** | **1.0s** |

Branch coverage: 100% (gate: 80%).
Planted bug (`hour <= 6`) was caught by `test_night_flag_boundaries[6-0]` (unit) and `test_golden_scores` (182 rows, behavioural).

## CI pipeline (GitHub Actions, ubuntu-latest)

| Job | First run on main | Latest run on main |
|---|---|---|
| lint | 34s | 42s |
| test | 48s | 49s |
| image-smoke | 116s | 30s |
| publish | 27s | 21s |

image-smoke is ~4x faster on the second run because Docker layers are cached
between runs (`cache-from: type=gha`): the dependency layer is reused.

A bad PR (layer violation + `hour <= 6`) was blocked: `lint` failed at Ruff (I001: the
out-of-layer import broke the import order, so the later import-contract step never ran) and
`test` failed on `test_night_flag_boundaries[6-0]`; `image-smoke` and `publish` were skipped.
