import bisect
import os
import random
from pathlib import Path

from locust import FastHttpUser, constant_throughput, task

DEFAULT_ZIPF_EXPONENT = 1.1
DEFAULT_HOST = "https://aoi.rs"
DEFAULT_SLUG_FILE = Path(__file__).resolve().parents[1] / "slugs.txt"
DEFAULT_TARGET_RPS = 5.0


def load_slugs(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(
            f"Slug file not found at {path}. Generate it with 'uv run python scripts/create_links.py'."
        )

    slugs = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not slugs:
        raise ValueError(f"No slugs found in {path}. The benchmark needs a populated slugs.txt file.")

    return slugs


def build_zipf_cdf(slugs: list[str], exponent: float) -> list[float]:
    weights = [1.0 / (index**exponent) for index in range(1, len(slugs) + 1)]
    total_weight = sum(weights)
    if total_weight <= 0:
        raise ValueError("Zipf weights must be positive.")

    cdf = []
    running_total = 0.0
    for weight in weights:
        running_total += weight / total_weight
        cdf.append(running_total)
    return cdf


ZIPF_EXPONENT = float(os.getenv("ZIPF_EXPONENT", str(DEFAULT_ZIPF_EXPONENT)))
SLUGS = load_slugs(Path(os.getenv("AOI_SLUG_FILE", str(DEFAULT_SLUG_FILE))))
ZIPF_CDF = build_zipf_cdf(SLUGS, ZIPF_EXPONENT)


def choose_slug() -> str:
    if len(SLUGS) == 1:
        return SLUGS[0]

    roll = random.random()
    index = bisect.bisect_left(ZIPF_CDF, roll)
    return SLUGS[min(index, len(SLUGS) - 1)]


class RedirectUser(FastHttpUser):
    host = os.getenv("LOCUST_HOST", DEFAULT_HOST)
    wait_time = constant_throughput(float(os.getenv("LOCUST_TARGET_RPS", str(DEFAULT_TARGET_RPS))))

    @task
    def resolve_short_url(self) -> None:
        slug = choose_slug()

        with self.client.get(
            f"/{slug}",
            name="[Redirects] Resolve short URL",
            allow_redirects=False,
            catch_response=True,
        ) as response:
            if response.status_code in (301, 308):
                response.success()
            else:
                response.failure(f"Expected 301 or 308 redirect for /{slug}, got status {response.status_code}.")
