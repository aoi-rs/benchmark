# aoi.rs redirect benchmark

This repository benchmarks the production redirect path for aoi.rs with a small, reproducible Locust workload. The benchmark is intentionally simple: it measures the redirect flow as seen from a single load-generation node and is designed to exercise the real production path rather than a fake in-memory redirect implementation.

## What the benchmark measures

The workload measures the end-to-end redirect path:

client → CloudFront → redirect origin on cache miss

That means the benchmark is not measuring global CDN capacity. It is measuring how a single node behaves when it resolves a short link through the public aoi.rs entry point. Cached requests may never reach the Rust redirect service, so the benchmark is intentionally set up to hit the production redirect path and observe the latency and correctness of the redirect response.

## Why 10,000 links

The benchmark uses a catalog of 10,000 short links so it can model a realistic long-tail workload. A small group of URLs is hot and most requests land on a small subset, while the rest of the list remains cold but still present in the working set. This is closer to real short-link traffic than a uniform random sample.

## Zipfian traffic pattern

The redirect workload does not select slugs uniformly at random. It uses a Zipfian popularity distribution with a default exponent of 1.1. In practice, that means a relatively small subset of slugs receives most of the traffic while the remaining slugs still appear in the long tail.

The exponent is configurable through the environment variable `ZIPF_EXPONENT` when running Locust, and the CDF is built once at startup so the load generator does not recompute weights for every request.

## Generate links

Use the link-generation script to create 10,000 real short links in production through the aoi.rs REST API:

```bash
export AOI_PAT="<your-personal-access-token>"
uv run python scripts/create_links.py
```

Optional overrides:

```bash
uv run python scripts/create_links.py --count 15000
uv run python scripts/create_links.py --output ./custom_slugs.txt
```

The script writes one slug per line to `slugs.txt` and appends only successfully created links. If the file already contains some slugs, it resumes until the requested total count is reached instead of regenerating everything. The PAT is never printed and must be provided through `AOI_PAT` or `--pat`.

## Run the benchmark locally

From the repository root:

```bash
uv sync
uv run locust -f load_tests/locustfile.py --host https://aoi.rs --headless --users 400 --spawn-rate 40 --run-time 2m --csv results/aoi_redirects --html results/aoi_redirects.html
```

If you want to vary the Zipfian skew, set the exponent before starting Locust:

```bash
export ZIPF_EXPONENT=1.1
```

The benchmark expects `slugs.txt` to exist and to contain valid slugs. A valid redirect response is HTTP 301 or 308, and any other status is marked as a failed Locust response.

## GitHub Actions

The workflow in `.github/workflows/benchmark.yml` runs a headless Locust benchmark on a single `ubuntu-latest` runner. It installs `uv`, syncs dependencies from `pyproject.toml` and `uv.lock`, runs the benchmark against `https://aoi.rs`, and stores the CSV and HTML outputs in the `results/` directory.

The workflow uploads the results as an artifact named `aoi-load-test-results` and fails if Locust itself exits unsuccessfully.

This repository does not generate the 10,000 links during every CI run. The benchmark expects `slugs.txt` to already exist in the repository or to be provided via artifact/input before running the redirect test. This keeps CI runs focused on the redirect workload instead of the link-creation API path.

## Result storage

Benchmark results are written to the `results/` directory:

- `results/aoi_redirects.csv`
- `results/aoi_redirects_stats_history.csv`
- `results/aoi_redirects_failures.csv`
- `results/aoi_redirects.html`

## Notes

This is intentionally a one-node load-generation benchmark. It measures redirect behavior from a single load source, not global CloudFront capacity or aggregate edge throughput across the entire internet.
