#!/usr/bin/env python3
"""Write a schema-compatible sample of transaction_cat.parquet.

The course dataset (mitulshah/transaction-categorization) is gated on Hugging Face.
Use this when you cannot authenticate, so notebook 01 still runs. Row counts will
not match the saved notebook outputs.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "transaction_cat.parquet",
    )
    parser.add_argument("--rows", type=int, default=1_000_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    categories = np.array(
        [
            "groceries",
            "restaurants",
            "transport",
            "utilities",
            "entertainment",
            "health",
            "shopping",
            "travel",
            "education",
            "other",
        ]
    )
    countries = np.array(["USA", "UK", "Canada", "Australia", "India"])
    currencies = np.array(["USD", "GBP", "CAD", "AUD", "INR"])
    n = args.rows
    cidx = rng.integers(0, len(categories), size=n)
    nidx = rng.integers(0, len(countries), size=n)
    category = categories[cidx]
    country = countries[nidx]
    currency = currencies[nidx]
    desc = np.char.add(np.char.add(category, " merchant-"), nidx.astype(str))
    table = pa.table(
        {
            "transaction_description": pa.array(desc, type=pa.string()),
            "category": pa.array(category, type=pa.string()),
            "country": pa.array(country, type=pa.string()),
            "currency": pa.array(currency, type=pa.string()),
        }
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, args.out, compression="snappy", row_group_size=max(n // 4, 1))
    print(f"wrote {args.out} rows={n} bytes={args.out.stat().st_size}")


if __name__ == "__main__":
    main()
