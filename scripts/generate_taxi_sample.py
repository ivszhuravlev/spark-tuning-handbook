#!/usr/bin/env python3
"""Write schema-compatible NYC Yellow Taxi sample parquet files.

Use this on a laptop when you do not want to download a full year of TLC files.
Notebooks 03-05 will run; row counts and timings will differ from saved outputs.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


def build_table(n: int, seed: int, start: datetime) -> pa.Table:
    rng = np.random.default_rng(seed)
    pickup_off = rng.integers(0, 366 * 24 * 3600, size=n)
    trip_secs = rng.integers(60, 3600, size=n)
    pickup = np.array(
        [start + timedelta(seconds=int(s)) for s in pickup_off],
        dtype="datetime64[us]",
    )
    dropoff = pickup + trip_secs.astype("timedelta64[s]")
    loc = rng.integers(1, 266, size=n, dtype=np.int32)
    fare = rng.uniform(3.0, 80.0, size=n)
    tip = fare * rng.uniform(0.0, 0.3, size=n)
    extra = np.where(rng.random(n) < 0.4, 1.0, 0.0)
    mta = np.full(n, 0.5)
    tolls = np.where(rng.random(n) < 0.05, rng.uniform(2.0, 8.0, size=n), 0.0)
    improvement = np.full(n, 1.0)
    congestion = np.where(rng.random(n) < 0.6, 2.5, 0.0)
    airport = np.where(np.isin(loc, [1, 132, 138]), 1.75, 0.0)
    total = fare + tip + extra + mta + tolls + improvement + congestion + airport
    vendor = rng.choice(np.array([1, 2], dtype=np.int32), size=n)
    passengers = rng.integers(1, 5, size=n, dtype=np.int64)
    distance = rng.uniform(0.3, 25.0, size=n)
    ratecode = np.where(airport > 0, 2, 1).astype(np.int64)
    payment = rng.choice(np.array([1, 2, 3, 4], dtype=np.int64), size=n)
    flag = np.where(rng.random(n) < 0.01, "Y", "N")

    return pa.table(
        {
            "VendorID": pa.array(vendor, type=pa.int32()),
            "tpep_pickup_datetime": pa.array(pickup),
            "tpep_dropoff_datetime": pa.array(dropoff),
            "passenger_count": pa.array(passengers, type=pa.int64()),
            "trip_distance": pa.array(distance, type=pa.float64()),
            "RatecodeID": pa.array(ratecode, type=pa.int64()),
            "store_and_fwd_flag": pa.array(flag, type=pa.string()),
            "PULocationID": pa.array(loc, type=pa.int32()),
            "DOLocationID": pa.array(rng.integers(1, 266, size=n, dtype=np.int32), type=pa.int32()),
            "payment_type": pa.array(payment, type=pa.int64()),
            "fare_amount": pa.array(fare, type=pa.float64()),
            "extra": pa.array(extra, type=pa.float64()),
            "mta_tax": pa.array(mta, type=pa.float64()),
            "tip_amount": pa.array(tip, type=pa.float64()),
            "tolls_amount": pa.array(tolls, type=pa.float64()),
            "improvement_surcharge": pa.array(improvement, type=pa.float64()),
            "total_amount": pa.array(total, type=pa.float64()),
            "congestion_surcharge": pa.array(congestion, type=pa.float64()),
            "Airport_fee": pa.array(airport, type=pa.float64()),
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "taxi",
    )
    parser.add_argument("--rows", type=int, default=400_000)
    parser.add_argument("--files", type=int, default=2)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    per = max(args.rows // args.files, 1)
    start = datetime(2024, 1, 1)
    written = 0
    for i in range(args.files):
        n = per if i < args.files - 1 else args.rows - per * (args.files - 1)
        table = build_table(n, args.seed + i, start)
        dest = args.out_dir / f"yellow_tripdata_sample_{i + 1:02d}.parquet"
        pq.write_table(table, dest, compression="snappy")
        written += n
        print(f"wrote {dest} rows={n} bytes={dest.stat().st_size}")
    print(f"taxi sample total rows={written} dir={args.out_dir}")


if __name__ == "__main__":
    main()
