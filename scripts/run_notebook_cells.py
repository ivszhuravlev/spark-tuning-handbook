#!/usr/bin/env python3
"""Execute code cells of a course notebook against a live SparkSession.

Strips IPython magics (%%time) so the notebook can run outside Jupyter.
Creates a SparkSession if `spark` is not already in the namespace.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


MAGIC = re.compile(r"^%%\w+.*\n", re.M)


def create_spark(app_name: str):
    from pyspark.sql import SparkSession
    import socket

    master = os.getenv("SPARK_MASTER")
    if not master:
        try:
            socket.getaddrinfo("spark-master", 7077)
            master = "spark://spark-master:7077"
        except OSError:
            master = "spark://127.0.0.1:7077"
    builder = (
        SparkSession.builder.appName(app_name)
        .master(master)
        .config("spark.sql.adaptive.enabled", "false")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.sql.catalogImplementation", "hive")
        .config("spark.sql.warehouse.dir", os.getenv("SPARK_WAREHOUSE", "/opt/spark/work-dir/spark-warehouse"))
        .config("spark.executor.memory", os.getenv("SPARK_EXECUTOR_MEMORY", "2g"))
        .config("spark.ui.port", os.getenv("SPARK_APP_UI_PORT", "4040"))
    )
    driver_host = os.getenv("SPARK_DRIVER_HOST")
    if driver_host:
        builder = builder.config("spark.driver.host", driver_host).config(
            "spark.driver.bindAddress", os.getenv("SPARK_DRIVER_BIND", "0.0.0.0")
        )
    return builder.getOrCreate()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("notebook", type=Path)
    parser.add_argument("--app-name", default="spark-tuning-handbook")
    args = parser.parse_args()

    nb_path = args.notebook.resolve()
    os.chdir(nb_path.parent)
    nb = json.loads(nb_path.read_text())
    ns = {"__name__": "__main__"}
    ns["spark"] = create_spark(args.app_name)

    cell_i = 0
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        cell_i += 1
        src = MAGIC.sub("", "".join(cell.get("source", []))).strip()
        if not src:
            continue
        print(f"\n===== cell {cell_i} =====", flush=True)
        try:
            exec(compile(src, f"{nb_path.name}:cell{cell_i}", "exec"), ns)
        except Exception as exc:
            print(f"FAILED cell {cell_i}: {type(exc).__name__}: {exc}", file=sys.stderr)
            ns["spark"].stop()
            return 1
        print(f"===== cell {cell_i} ok =====", flush=True)

    print("\nAll code cells completed.", flush=True)
    ns["spark"].stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
