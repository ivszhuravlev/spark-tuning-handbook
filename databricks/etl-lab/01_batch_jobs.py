# Databricks notebook source
# MAGIC %md
# MAGIC # Batch jobs
# MAGIC
# MAGIC Five jobs. Input table and output schema are in the widgets. Setup writes run metrics next to the schema location.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup

# COMMAND ----------

import importlib
import json
import sys
import time
import traceback

from pyspark.sql import functions as F

dbutils.widgets.text(
    "txn_path",
    "hive_metastore.spark_tuning_test.transactions",
)
dbutils.widgets.text(
    "out_dir",
    "hive_metastore.spark_tuning_test",
)
dbutils.widgets.text(
    "jobs_dir",
    "",
)

TXN_PATH = dbutils.widgets.get("txn_path").strip()
OUT_DIR = dbutils.widgets.get("out_dir").strip().rstrip("/")
JOBS_DIR = dbutils.widgets.get("jobs_dir").strip()

REQUIRED_COLS = ["transaction_description", "category", "country", "currency"]

print("spark.version:", spark.version)
print("applicationId:", spark.sparkContext.applicationId)
print("txn_path:", TXN_PATH)
print("out_dir:", OUT_DIR)
print("jobs_dir:", JOBS_DIR)

# COMMAND ----------

def _try_set_conf(key, value):
    try:
        spark.conf.set(key, value)
    except Exception as exc:
        print(f"could not set {key}={value}: {type(exc).__name__}: {exc}")
        return
    actual = spark.conf.get(key)
    print(f"conf {key}={actual}")
    if str(actual).lower() != str(value).lower():
        print(f"{key} actual={actual} requested={value}")


_try_set_conf("spark.sql.adaptive.enabled", "false")
_try_set_conf("spark.sql.shuffle.partitions", "8")

# COMMAND ----------

def _is_table_name(name):
    return "/" not in name and not name.startswith("dbfs:")


def _schema_location(schema):
    try:
        for row in spark.sql(f"DESCRIBE DATABASE EXTENDED {schema}").collect():
            item = str(row[0]).strip().lower()
            if item in ("location", "locationuri"):
                return str(row[1]).strip()
    except Exception:
        return None
    return None


def _generate_txn_df(n=200000):
    categories = [
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
    countries = ["USA", "UK", "Canada", "Australia", "India"]
    currencies = ["USD", "GBP", "CAD", "AUD", "INR"]
    cat_arr = F.array(*[F.lit(x) for x in categories])
    country_arr = F.array(*[F.lit(x) for x in countries])
    currency_arr = F.array(*[F.lit(x) for x in currencies])
    return (
        spark.range(n)
        .withColumn("cidx", (F.rand(42) * len(categories)).cast("int"))
        .withColumn("nidx", (F.rand(43) * len(countries)).cast("int"))
        .withColumn("category", F.element_at(cat_arr, F.col("cidx") + 1))
        .withColumn("country", F.element_at(country_arr, F.col("nidx") + 1))
        .withColumn("currency", F.element_at(currency_arr, F.col("nidx") + 1))
        .withColumn(
            "transaction_description",
            F.concat(F.col("category"), F.lit(" merchant-"), F.col("nidx").cast("string")),
        )
        .select("transaction_description", "category", "country", "currency")
    )


def ensure_txn(name):
    schema = name.rsplit(".", 1)[0] if _is_table_name(name) and name.count(".") >= 1 else OUT_DIR
    if _is_table_name(schema):
        spark.sql(f"CREATE DATABASE IF NOT EXISTS {schema}")
    if _is_table_name(name):
        try:
            df = spark.table(name)
        except Exception:
            _generate_txn_df().write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(name)
            print(f"wrote table {name}")
            df = spark.table(name)
    else:
        try:
            df = spark.read.parquet(name)
        except Exception:
            _generate_txn_df().write.mode("overwrite").saveAsTable(
                "hive_metastore.spark_tuning_test.transactions"
            )
            df = spark.table("hive_metastore.spark_tuning_test.transactions")
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{name} missing columns {missing}; have {df.columns}")
    n = df.count()
    print("input:", name)
    print("input columns:", df.columns)
    print("input row count:", n)
    df.printSchema()
    spark.sql(f"SHOW TABLES IN {OUT_DIR}").show(truncate=False)
    return n


if _is_table_name(OUT_DIR):
    spark.sql(f"CREATE DATABASE IF NOT EXISTS {OUT_DIR}")
INPUT_ROWS = ensure_txn(TXN_PATH)

# COMMAND ----------

def cluster_note():
    keys = [
        "spark.databricks.clusterUsageTags.sparkVersion",
        "spark.databricks.clusterUsageTags.clusterName",
        "spark.databricks.clusterUsageTags.clusterId",
        "spark.databricks.clusterUsageTags.driverNodeType",
        "spark.databricks.clusterUsageTags.workerNodeType",
        "spark.databricks.clusterUsageTags.clusterMinWorkers",
        "spark.databricks.clusterUsageTags.clusterMaxWorkers",
        "spark.databricks.clusterUsageTags.clusterTargetWorkers",
        "spark.executor.cores",
        "spark.sql.adaptive.enabled",
        "spark.sql.shuffle.partitions",
    ]
    note = {"spark.version": spark.version}
    for key in keys:
        try:
            note[key] = spark.conf.get(key)
        except Exception:
            continue
    return note


CLUSTER_NOTE = cluster_note()
print(json.dumps(CLUSTER_NOTE, indent=2))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Jobs

# COMMAND ----------

if JOBS_DIR not in sys.path:
    sys.path.insert(0, JOBS_DIR)

import country_overlap
import daily_txn_enrich
import fx_lookup_join
import hotkey_rollup
import qc_reject

for _mod in (daily_txn_enrich, fx_lookup_join, hotkey_rollup, country_overlap, qc_reject):
    importlib.reload(_mod)

JOBS = [
    ("daily_txn_enrich", daily_txn_enrich.run),
    ("fx_lookup_join", fx_lookup_join.run),
    ("hotkey_rollup", hotkey_rollup.run),
    ("country_overlap", country_overlap.run),
    ("qc_reject", qc_reject.run),
]

print("loaded:", [name for name, _ in JOBS])

# COMMAND ----------

def _java_call(obj, names):
    for name in names:
        if obj is None or not hasattr(obj, name):
            continue
        attr = getattr(obj, name)
        try:
            return attr() if callable(attr) else attr
        except Exception:
            continue
    return None


def _java_iter(jlist):
    if jlist is None:
        return
    if hasattr(jlist, "size"):
        for i in range(int(jlist.size())):
            if hasattr(jlist, "apply"):
                yield jlist.apply(i)
            else:
                yield jlist.get(i)
        return
    try:
        for item in jlist:
            yield item
    except Exception:
        return


def _status_store():
    try:
        return spark._jsparkSession.sharedState().statusStore()
    except Exception:
        return None


def _empty_option():
    try:
        return spark._jvm.scala.Option.empty()
    except Exception:
        return None


def tracker_metrics(job_group):
    tracker = spark.sparkContext.statusTracker()
    job_ids = list(tracker.getJobIdsForGroup(job_group) or [])
    max_tasks = 0
    failed_tasks = 0
    stages = []
    for jid in job_ids:
        jinfo = tracker.getJobInfo(jid)
        if jinfo is None:
            continue
        for sid in list(getattr(jinfo, "stageIds", []) or []):
            sinfo = tracker.getStageInfo(int(sid))
            if sinfo is None:
                continue
            n_tasks = int(sinfo.numTasks or 0)
            n_fail = int(sinfo.numFailedTasks or 0)
            max_tasks = max(max_tasks, n_tasks)
            failed_tasks += n_fail
            stages.append(
                {
                    "stageId": int(sinfo.stageId),
                    "name": sinfo.name,
                    "numTasks": n_tasks,
                    "numFailedTasks": n_fail,
                    "numCompletedTasks": int(getattr(sinfo, "numCompletedTasks", 0) or 0),
                }
            )
    return {
        "job_ids": [int(x) for x in job_ids],
        "max_tasks": max_tasks,
        "failed_tasks": failed_tasks,
        "stages": stages,
    }


def _stage_shuffle_fields(st):
    read = _java_call(st, ["shuffleReadBytes", "shuffleBytesRead"])
    write = _java_call(st, ["shuffleBytesWritten", "shuffleWriteBytes"])
    if read is None:
        srm = _java_call(st, ["shuffleReadMetrics"])
        read = _java_call(srm, ["bytesRead", "readBytes", "totalBytesRead"])
    if write is None:
        swm = _java_call(st, ["shuffleWriteMetrics"])
        write = _java_call(swm, ["bytesWritten", "writeBytes"])
    return int(read or 0), int(write or 0)


def store_stage_shuffle(stage_ids=None):
    store = _status_store()
    out = {}
    if store is None:
        return out
    ids = [int(x) for x in (stage_ids or [])]
    for sid in ids:
        st = None
        try:
            opt = store.stage(sid)
            defined = True
            if hasattr(opt, "isDefined"):
                defined = bool(opt.isDefined())
            elif hasattr(opt, "isEmpty"):
                defined = not bool(opt.isEmpty())
            if defined:
                st = opt.get()
        except Exception:
            st = None
        if st is None:
            continue
        read, write = _stage_shuffle_fields(st)
        out[sid] = {
            "shuffle_read_bytes": read,
            "shuffle_write_bytes": write,
            "numTasks": int(_java_call(st, ["numTasks"]) or 0),
            "numFailedTasks": int(_java_call(st, ["numFailedTasks"]) or 0),
        }
    if out:
        return out
    stage_list = None
    try:
        stage_list = store.stageList(_empty_option())
    except Exception:
        for meth in ("completedList", "activeStages", "failedList"):
            if hasattr(store, meth):
                try:
                    stage_list = getattr(store, meth)()
                    break
                except Exception:
                    continue
    for st in _java_iter(stage_list):
        sid = _java_call(st, ["stageId"])
        if sid is None:
            continue
        read, write = _stage_shuffle_fields(st)
        out[int(sid)] = {
            "shuffle_read_bytes": read,
            "shuffle_write_bytes": write,
            "numTasks": int(_java_call(st, ["numTasks"]) or 0),
            "numFailedTasks": int(_java_call(st, ["numFailedTasks"]) or 0),
        }
    return out


def store_plans():
    store = _status_store()
    plans = []
    if store is None:
        return plans
    execs = None
    for meth in ("executionsList", "sqlList"):
        if hasattr(store, meth):
            try:
                execs = getattr(store, meth)()
                break
            except Exception:
                continue
    for item in _java_iter(execs):
        plan = _java_call(
            item,
            ["physicalPlanDescription", "planDescription", "description"],
        )
        if plan:
            plans.append(str(plan))
    return plans


def plan_flags(plan_text):
    text = plan_text or ""
    return {
        "sort_merge": "SortMergeJoin" in text,
        "broadcast": ("BroadcastHashJoin" in text) or ("BroadcastExchange" in text),
        "exchange": "Exchange" in text,
        "plan_head": text[:4000],
    }


class _PlanListener(object):
    class Java:
        implements = ["org.apache.spark.sql.util.QueryExecutionListener"]

    def __init__(self, bucket):
        self.bucket = bucket

    def onSuccess(self, funcName, qe, durationNs):
        try:
            self.bucket.append(qe.executedPlan().toString())
        except Exception:
            pass

    def onFailure(self, funcName, qe, exception):
        try:
            self.bucket.append(qe.executedPlan().toString())
        except Exception:
            pass


_PLAN_BUCKET = []
_LISTENER = None
try:
    _LISTENER = _PlanListener(_PLAN_BUCKET)
    spark._jsparkSession.listenerManager().register(_LISTENER)
except Exception as exc:
    print(f"listener skipped: {type(exc).__name__}: {exc}")


def run_one(name, fn):
    spark.sparkContext.setJobGroup(name, name)
    n_plans_before = len(_PLAN_BUCKET)
    t0 = time.perf_counter()
    ok = False
    rows = None
    error = None
    try:
        rows = fn(spark, TXN_PATH, OUT_DIR)
        ok = True
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        print(f"{name}: {error[:800]}")
        traceback.print_exc()
    wall = round(time.perf_counter() - t0, 3)

    tracked = tracker_metrics(name)
    stage_ids = [st["stageId"] for st in tracked["stages"]]
    shuffle_map = store_stage_shuffle(stage_ids)
    shuffle_read = 0
    shuffle_write = 0
    for sid in stage_ids:
        extra = shuffle_map.get(sid, {})
        shuffle_read += int(extra.get("shuffle_read_bytes") or 0)
        shuffle_write += int(extra.get("shuffle_write_bytes") or 0)
    if shuffle_read == 0 and shuffle_write == 0 and shuffle_map:
        for extra in shuffle_map.values():
            shuffle_read += int(extra.get("shuffle_read_bytes") or 0)
            shuffle_write += int(extra.get("shuffle_write_bytes") or 0)

    listener_plans = _PLAN_BUCKET[n_plans_before:]
    store_plan_text = "\n".join(store_plans()[-8:])
    plan_text = "\n".join(listener_plans) or store_plan_text
    flags = plan_flags(plan_text)

    row = {
        "job": name,
        "wall_time_sec": wall,
        "ok": ok,
        "rows": rows,
        "error": error,
        "max_tasks": tracked["max_tasks"],
        "shuffle_read_bytes": shuffle_read,
        "shuffle_write_bytes": shuffle_write,
        "sort_merge": flags["sort_merge"],
        "broadcast": flags["broadcast"],
        "failed_tasks": tracked["failed_tasks"],
        "job_ids": tracked["job_ids"],
        "plan_head": flags["plan_head"],
    }
    print(
        f"{name} wall={wall}s ok={ok} rows={rows} max_tasks={row['max_tasks']} "
        f"failed_tasks={row['failed_tasks']} shuffle_read_bytes={shuffle_read} "
        f"shuffle_write_bytes={shuffle_write} sort_merge={row['sort_merge']} broadcast={row['broadcast']}"
    )
    return row

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run

# COMMAND ----------

baseline_rows = []
for _name, _fn in JOBS:
    baseline_rows.append(run_one(_name, _fn))

baseline_payload = {
    "input_row_count": INPUT_ROWS,
    "txn_path": TXN_PATH,
    "out_dir": OUT_DIR,
    "cluster": CLUSTER_NOTE,
    "jobs": baseline_rows,
}

_metrics_loc = _schema_location(OUT_DIR) if _is_table_name(OUT_DIR) else OUT_DIR
if not _metrics_loc:
    _metrics_loc = "dbfs:/user/hive/warehouse/spark_tuning_test.db"
metrics_path = _metrics_loc.rstrip("/") + "/baseline_metrics.json"
dbutils.fs.put(metrics_path, json.dumps(baseline_payload, indent=2, default=str), True)
print("wrote", metrics_path)
spark.sql(f"SHOW TABLES IN {OUT_DIR}").show(truncate=False)

baseline_table = spark.createDataFrame(
    [
        {
            "job": r["job"],
            "wall_time_sec": float(r["wall_time_sec"]),
            "ok": bool(r["ok"]),
            "rows": int(r["rows"]) if r["rows"] is not None else None,
            "error": r["error"],
            "max_tasks": int(r["max_tasks"]),
            "shuffle_read_bytes": int(r["shuffle_read_bytes"]),
            "shuffle_write_bytes": int(r["shuffle_write_bytes"]),
            "sort_merge": bool(r["sort_merge"]),
            "broadcast": bool(r["broadcast"]),
            "failed_tasks": int(r["failed_tasks"]),
        }
        for r in baseline_rows
    ]
)
display(baseline_table)
