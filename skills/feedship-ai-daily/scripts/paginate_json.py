#!/usr/bin/env python3
"""
Paginate JSON items into batches.

Usage:
    cat data.json | python paginate_json.py [--size 200]
    python paginate_json.py --size 200 < data.json
"""

import argparse
import json
import sys
from typing import Any


def paginate(data: dict[str, Any], batch_size: int) -> list[dict[str, Any]]:
    """Paginate JSON data into batches."""
    items = data.get("items", [])
    batches = []

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        batch_data = {
            "items": batch,
            "count": len(batch),
            "limit": batch_size,
            "has_more": i + batch_size < len(items),
            "page": i // batch_size + 1,
            "total": len(items),
        }
        batches.append(batch_data)

    return batches


def main():
    parser = argparse.ArgumentParser(description="Paginate JSON items")
    parser.add_argument(
        "--size", type=int, default=200, help="Batch size (default: 200)"
    )
    parser.add_argument(
        "--dry", action="store_true", help="Show what would be generated"
    )
    args = parser.parse_args()

    data = json.load(sys.stdin)
    batches = paginate(data, args.size)

    if args.dry:
        print(f"Would generate {len(batches)} batches:")
        for i, batch in enumerate(batches):
            print(
                f"  Batch {i + 1}: {batch['count']} items (has_more={batch['has_more']})"
            )
        return

    # Output all batches as JSON array
    print(json.dumps(batches, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
