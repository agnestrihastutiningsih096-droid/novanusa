from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from typing import Any


SOURCE_ENDPOINT = "https://sirup.inaproc.id/sirup/caripaketctr/search"
SOURCE_PAGE = "https://sirup.inaproc.id/sirup/caripaketctr/index"
PAGE_NUMBERS = range(4)
MAX_PAGE_SIZE = 100


def fetch_page(year: int, page_number: int, page_size: int, timeout: float) -> dict[str, Any]:
    params = {
        "tahunAnggaran": year,
        "jenisPengadaan": "",
        "metodePengadaan": "",
        "minPagu": "",
        "maxPagu": "",
        "bulan": "",
        "lokasi": "",
        "kldi": "",
        "pdn": "",
        "ukm": "",
        "draw": page_number + 1,
        "start": page_number * page_size,
        "length": page_size,
        "order[0][column]": 11,
        "order[0][dir]": "desc",
        "search[value]": "",
        "search[regex]": "false",
    }
    request = urllib.request.Request(
        f"{SOURCE_ENDPOINT}?{urllib.parse.urlencode(params)}",
        headers={
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": SOURCE_PAGE,
            "User-Agent": "NovaNusa-SiRUP-Pagination-Validator/1.0",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"page {page_number}: unexpected HTTP status {response.status}")
        if response.headers.get_content_type() != "application/json":
            raise RuntimeError(
                f"page {page_number}: unexpected content type "
                f"{response.headers.get_content_type()!r}"
            )
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise RuntimeError(f"page {page_number}: malformed response shape")
    if not isinstance(payload.get("recordsFiltered"), int):
        raise RuntimeError(f"page {page_number}: recordsFiltered is not an integer")
    return payload


def validate_pages(pages: list[dict[str, Any]], page_size: int) -> tuple[dict[str, Any], bool]:
    page_ids: list[list[int]] = []
    page_size_failures: list[dict[str, int]] = []
    gap_pages: list[int] = []
    ordering_failures: list[dict[str, Any]] = []
    source_counts: list[int] = []

    for page_number, payload in enumerate(pages):
        rows = payload["data"]
        source_counts.append(payload["recordsFiltered"])
        if len(rows) != page_size:
            page_size_failures.append(
                {"page": page_number, "expected": page_size, "actual": len(rows)}
            )
            gap_pages.append(page_number)
        ids: list[int] = []
        for row_number, row in enumerate(rows):
            if not isinstance(row, dict) or row.get("id") is None:
                raise RuntimeError(f"page {page_number}, row {row_number}: missing ID")
            try:
                ids.append(int(row["id"]))
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"page {page_number}, row {row_number}: invalid ID {row['id']!r}"
                ) from exc
        if any(left <= right for left, right in zip(ids, ids[1:])):
            ordering_failures.append({"page": page_number, "reason": "not_strict_id_desc"})
        page_ids.append(ids)

    for page_number in range(1, len(page_ids)):
        previous = page_ids[page_number - 1]
        current = page_ids[page_number]
        if previous and current and previous[-1] <= current[0]:
            ordering_failures.append(
                {
                    "boundary": [page_number - 1, page_number],
                    "previous_last_id": previous[-1],
                    "current_first_id": current[0],
                }
            )

    all_ids = [identifier for ids in page_ids for identifier in ids]
    counts = Counter(all_ids)
    duplicate_ids = sorted(identifier for identifier, count in counts.items() if count > 1)
    overlap = []
    for left in range(len(page_ids)):
        for right in range(left + 1, len(page_ids)):
            shared = sorted(set(page_ids[left]) & set(page_ids[right]))
            if shared:
                overlap.append({"pages": [left, right], "ids": shared})

    source_count_consistent = len(set(source_counts)) == 1
    expected_offsets = [page_number * page_size for page_number in PAGE_NUMBERS]
    result = {
        "pages_fetched": list(PAGE_NUMBERS),
        "page_size": page_size,
        "offsets": expected_offsets,
        "rows_received": [len(ids) for ids in page_ids],
        "page_size_valid": not page_size_failures,
        "page_size_failures": page_size_failures,
        "duplicate_ids": duplicate_ids,
        "overlap": overlap,
        "gaps": gap_pages,
        "ordering": {
            "requested": "id DESC",
            "valid": not ordering_failures,
            "failures": ordering_failures,
        },
        "source_records_filtered": source_counts,
        "source_count_consistent": source_count_consistent,
    }
    passed = (
        not page_size_failures
        and not duplicate_ids
        and not overlap
        and not gap_pages
        and not ordering_failures
        and source_count_consistent
    )
    return result, passed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate exactly four bounded SiRUP pages without writing artifacts."
    )
    parser.add_argument("--year", type=int, required=True, help="Explicit SiRUP budget year.")
    parser.add_argument("--page-size", type=int, default=10, help="Rows per page (1-100).")
    parser.add_argument("--timeout", type=float, default=30, help="Request timeout (1-60 seconds).")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between pages (0-5 seconds).")
    args = parser.parse_args()
    if not 1 <= args.page_size <= MAX_PAGE_SIZE:
        parser.error(f"--page-size must be between 1 and {MAX_PAGE_SIZE}")
    if not 1 <= args.timeout <= 60:
        parser.error("--timeout must be between 1 and 60 seconds")
    if not 0 <= args.delay <= 5:
        parser.error("--delay must be between 0 and 5 seconds")
    return args


def main() -> int:
    args = parse_args()
    pages: list[dict[str, Any]] = []
    try:
        for page_number in PAGE_NUMBERS:
            pages.append(fetch_page(args.year, page_number, args.page_size, args.timeout))
            if page_number < max(PAGE_NUMBERS):
                time.sleep(args.delay)
        result, passed = validate_pages(pages, args.page_size)
    except (OSError, UnicodeError, json.JSONDecodeError, RuntimeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed" if passed else "failed", **result}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
