#!/usr/bin/env python3
"""Submit the skill-test workloads against the handbook Spark cluster."""

from __future__ import annotations

import json
import os
import socket
import sys
import time
import traceback
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill-tests"))

from workloads import country_overlap, daily_txn_enrich, fx_lookup_join, hotkey_rollup, qc_reject


def data_dir() -> Path:
    env = os.getenv("SPARK_TUNING_DATA_DIR")
    return Path(env) if env else ROOT / "data"


def txn_path() -> Path:
    path = data_dir() / "transaction_cat.parquet"
    if not path.exists():
        raise SystemExit(
            f"missing {path}\n"
            "Create samples with: python scripts/prepare_local_data.py\n"
            "From Docker: docker compose exec jupyter python /scripts/prepare_local_data.py"
        )
    return path


def default_master() -> str:
    env = os.getenv("SPARK_MASTER")
    if env:
        return env
    try:
        socket.getaddrinfo("spark-master", 7077)
        return "spark://spark-master:7077"
    except OSError:
        return "spark://127.0.0.1:7077"


def create_spark():
    from pyspark.sql import SparkSession

    existing = SparkSession.getActiveSession()
    if existing is not None:
        existing.conf.set("spark.sql.adaptive.enabled", "false")
        existing.conf.set("spark.sql.shuffle.partitions", "8")
        return existing, False

    master = default_master()
    ui_port = os.getenv("SPARK_APP_UI_PORT", "4040")
    builder = (
        SparkSession.builder.appName("handbook-skill-tests")
        .master(master)
        .config("spark.sql.adaptive.enabled", "false")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.executor.memory", os.getenv("SPARK_EXECUTOR_MEMORY", "2g"))
        .config("spark.ui.port", ui_port)
        .config("spark.ui.showConsoleProgress", "true")
    )
    driver_host = os.getenv("SPARK_DRIVER_HOST")
    if driver_host:
        builder = builder.config("spark.driver.host", driver_host).config(
            "spark.driver.bindAddress", os.getenv("SPARK_DRIVER_BIND", "0.0.0.0")
        )
    return builder.getOrCreate(), True


def ui_base(spark) -> str:
    url = spark.sparkContext.uiWebUrl or f"http://127.0.0.1:{os.getenv('SPARK_APP_UI_PORT', '4040')}"
    return url.rstrip("/")


def fetch_json(url: str):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode())


def stage_quantiles(api: str, app_id: str, stage_id: int) -> dict | None:
    q = urllib.parse.urlencode({"quantiles": "0.0,0.5,0.95,1.0"})
    for attempt in (0, 1, 2):
        url = f"{api}/applications/{app_id}/stages/{stage_id}/{attempt}/taskSummary?{q}"
        try:
            return fetch_json(url)
        except Exception:
            continue
    return None


def snapshot(spark) -> dict:
    base = ui_base(spark)
    api = f"{base}/api/v1"
    app_id = spark.sparkContext.applicationId
    jobs = fetch_json(f"{api}/applications/{app_id}/jobs")
    stages = fetch_json(f"{api}/applications/{app_id}/stages?details=false")
    try:
        sqls = fetch_json(f"{api}/applications/{app_id}/sql")
    except Exception:
        sqls = []

    slim_jobs = [
        {
            "jobId": j.get("jobId"),
            "name": j.get("name"),
            "status": j.get("status"),
            "numTasks": j.get("numTasks"),
            "numFailedTasks": j.get("numFailedTasks"),
            "stageIds": j.get("stageIds"),
        }
        for j in jobs
    ]
    slim_stages = []
    for s in stages:
        row = {
            "stageId": s.get("stageId"),
            "status": s.get("status"),
            "numTasks": s.get("numTasks"),
            "numFailedTasks": s.get("numFailedTasks"),
            "shuffleWriteBytes": s.get("shuffleWriteBytes"),
            "shuffleReadBytes": s.get("shuffleReadBytes"),
            "executorRunTime": s.get("executorRunTime"),
            "memoryBytesSpilled": s.get("memoryBytesSpilled"),
            "diskBytesSpilled": s.get("diskBytesSpilled"),
            "description": (s.get("description") or "")[:160],
            "name": (s.get("name") or "")[:120],
        }
        if (s.get("numTasks") or 0) >= 4 and s.get("status") in {"COMPLETE", "FAILED", "SUCCESS"}:
            summary = stage_quantiles(api, app_id, int(s["stageId"]))
            if isinstance(summary, dict):
                row["taskRuntime"] = summary.get("executorRunTime")
                row["taskShuffleRead"] = (summary.get("shuffleReadMetrics") or {}).get("readBytes")
                row["taskShuffleWrite"] = (summary.get("shuffleWriteMetrics") or {}).get("bytesWritten")
        slim_stages.append(row)

    sql_slim = []
    if isinstance(sqls, list):
        for item in sqls[:40]:
            plan = item.get("planDescription") or item.get("description") or ""
            sql_slim.append(
                {
                    "id": item.get("id"),
                    "duration": item.get("duration"),
                    "success": item.get("success", item.get("status")),
                    "description": (item.get("description") or "")[:160],
                    "sortMerge": "SortMergeJoin" in plan,
                    "broadcast": "BroadcastHashJoin" in plan or "BroadcastExchange" in plan,
                    "exchange": "Exchange" in plan,
                    "python": "Python" in plan,
                    "planHead": plan[:500],
                }
            )

    return {
        "ui": base,
        "appId": app_id,
        "jobs": slim_jobs,
        "stages": slim_stages,
        "sql": sql_slim,
    }


def main() -> int:
    out_dir = os.getenv("SKILL_TEST_OUT", str(data_dir() / "tmp" / "skill-tests-out"))
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = str(txn_path())
    spark, owned = create_spark()
    print("UI", ui_base(spark))
    print("app", spark.sparkContext.applicationId)
    print("master", spark.sparkContext.master)
    print("txn", path)
    print("out", out_dir)

    runs = [
        ("daily_txn_enrich", daily_txn_enrich.run),
        ("fx_lookup_join", fx_lookup_join.run),
        ("hotkey_rollup", hotkey_rollup.run),
        ("country_overlap", country_overlap.run),
        ("qc_reject", qc_reject.run),
    ]
    results = []
    for name, fn in runs:
        t0 = time.time()
        try:
            n = fn(spark, path, out_dir)
            results.append({"name": name, "ok": True, "rows": n, "sec": round(time.time() - t0, 2)})
            print(f"OK {name} rows={n} sec={results[-1]['sec']}")
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            results.append({"name": name, "ok": False, "error": msg[:800], "sec": round(time.time() - t0, 2)})
            print(f"FAIL {name}: {msg[:400]}")
            traceback.print_exc()

    snap = snapshot(spark)
    snap["results"] = results
    dest = Path(os.getenv("SKILL_TEST_SNAPSHOT", "/tmp/skill-tests-snapshot.json"))
    dest.write_text(json.dumps(snap, indent=2, default=str))
    print("snapshot", dest)

    keep = os.getenv("SKILL_TEST_KEEP_UI") == "1"
    if keep:
        print("KEEP_UI=1 — Spark UI left up. Ctrl+C to stop.")
        try:
            while True:
                time.sleep(30)
        except KeyboardInterrupt:
            pass
    if owned and not keep:
        spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
