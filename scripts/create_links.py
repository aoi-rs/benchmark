#!/usr/bin/env python3

import argparse
import json
import os
from pathlib import Path
from urllib import error, request

API_URL = "https://service.aoi.rs/v1/links/"
DEFAULT_COUNT = 10_000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a fixed batch of short links from the production aoi.rs API."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        help=f"Total number of slugs to keep in the output file (default: {DEFAULT_COUNT}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "slugs.txt",
        help="Destination for the generated slugs; one slug per line.",
    )
    parser.add_argument(
        "--pat",
        default=os.getenv("AOI_PAT"),
        help="Bearer token for the AOI service. Defaults to the AOI_PAT environment variable.",
    )
    return parser.parse_args()


def load_existing_slugs(path: Path) -> set[str]:
    if not path.exists():
        return set()

    with path.open("r", encoding="utf-8") as handle:
        return {line.strip() for line in handle if line.strip()}


def create_link(pat: str, index: int) -> str:
    payload = {"destination_url": f"https://example.com/benchmark/{index}"}
    body = json.dumps(payload).encode("utf-8")

    req = request.Request(API_URL, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {pat}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

    try:
        with request.urlopen(req, timeout=30) as response:
            status = getattr(response, "status", response.getcode())
            raw_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        payload_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Unexpected HTTP status {exc.code} from {API_URL}: {payload_text[:500]}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Network error while creating a short link: {exc}") from exc

    if status not in (200, 201):
        raise RuntimeError(f"Unexpected HTTP status {status} from {API_URL}: {raw_body[:500]}")

    try:
        data = json.loads(raw_body or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Malformed JSON response from {API_URL}: {raw_body[:500]}") from exc

    slug = data.get("slug")
    if not isinstance(slug, str) or not slug.strip():
        raise RuntimeError(f"Malformed response from {API_URL}; expected 'slug' string, got: {raw_body[:500]}")

    return slug.strip()


def main() -> int:
    args = parse_args()
    count = args.count
    if count <= 0:
        raise SystemExit("--count must be a positive integer.")

    pat = args.pat or os.getenv("AOI_PAT")
    if not pat:
        raise SystemExit("AOI_PAT is required. Provide it as an environment variable or via --pat.")

    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    existing_slugs = load_existing_slugs(output_path)
    if len(existing_slugs) >= count:
        print(f"{len(existing_slugs)} slugs already exist in {output_path}; target count is {count}.")
        return 0

    next_index = len(existing_slugs)
    generated = 0

    with output_path.open("a", encoding="utf-8") as handle:
        while len(existing_slugs) + generated < count:
            index = next_index + generated
            slug = create_link(pat, index)
            if slug in existing_slugs:
                raise RuntimeError(f"Duplicate slug received from API: {slug}")
            handle.write(f"{slug}\n")
            handle.flush()
            generated += 1
            print(f"Generated slug {generated} / {count}")

    print(f"Wrote {generated} new slugs to {output_path}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - CLI friendliness
        raise SystemExit(f"ERROR: {exc}")
