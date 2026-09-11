#!/usr/bin/env python3
"""Create local sample datasets so the handbook runs without Hub tokens or TLC downloads.

Writes schema-compatible parquet under data/ (or --data-dir / SPARK_TUNING_DATA_DIR).
Existing files are left in place unless --force is set.
"""

from __future__ import annotations

import argparse
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(script: Path, argv: list[str]) -> None:
    sys.argv = [str(script), *argv]
    runpy.run_path(str(script), run_name="__main__")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.getenv("SPARK_TUNING_DATA_DIR", str(ROOT / "data"))),
    )
    parser.add_argument("--txn-rows", type=int, default=1_000_000)
    parser.add_argument("--taxi-rows", type=int, default=400_000)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    data = args.data_dir
    data.mkdir(parents=True, exist_ok=True)
    txn = data / "transaction_cat.parquet"
    taxi_dir = data / "taxi"

    if args.force or not txn.exists():
        _run(
            ROOT / "scripts" / "generate_transaction_cat_sample.py",
            ["--out", str(txn), "--rows", str(args.txn_rows)],
        )
    else:
        print(f"keep {txn}")

    taxi_files = list(taxi_dir.glob("*.parquet")) if taxi_dir.exists() else []
    if args.force or not taxi_files:
        _run(
            ROOT / "scripts" / "generate_taxi_sample.py",
            ["--out-dir", str(taxi_dir), "--rows", str(args.taxi_rows)],
        )
    else:
        print(f"keep {len(taxi_files)} taxi parquet file(s) in {taxi_dir}")

    print("data ready:")
    print(f"  {txn} exists={txn.exists()}")
    print(f"  {taxi_dir} parquet={len(list(taxi_dir.glob('*.parquet'))) if taxi_dir.exists() else 0}")


if __name__ == "__main__":
    main()
