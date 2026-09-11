---
name: spark-memory-troubleshooting
description: Spark unified memory, driver vs executor OOM, spill vs crash, broadcast memory, and Python UDF vs built-in vs Pandas UDF. Use when a job OOMs, spills, fails a task with a raised error, or a UDF shows BatchEvalPython (notebook 04).
---

# Memory management and troubleshooting

Source of truth: `notebooks/04_memory_management_and_troubleshooting.ipynb`.

## Unified memory (per executor JVM)

`spark.executor.memory` heap, minus ~300 MB reserved:

- **User memory** — `(1 - spark.memory.fraction)` for UDFs, metadata.
- **Unified** — `spark.memory.fraction` (default 0.6), split into execution + storage.

**Execution**: sorts, shuffle buffers, join/agg hash tables. Can **spill** to disk.

**Storage**: cache/persist and **broadcast** blocks.

Execution may evict storage **above** `spark.memory.storageFraction`. Execution cannot be evicted by storage. Broadcast hash tables in storage **do not spill**.

`spark.executor.memoryOverhead` is **off-heap** (Python workers, Netty). Pandas UDFs need pandas/pyarrow **on the executors**, not only on the driver image.

## Spill vs OOM

| | Spill | OOM |
| --- | --- | --- |
| What | Execution memory full; write temp files | Heap exhausted |
| Result | Job usually completes, slower | Driver or executor **dies** |
| UI | Task Spill (Memory)/(Disk) | Executor lost / `java.lang.OutOfMemoryError` |

Do not treat spill as a crash. Do not treat a SQL `raise_error` as an OOM.

## Driver vs executor OOM

**Driver** (`spark.driver.memory`): `collect()`, `toPandas()`, or collecting a broadcast that is too large. Fix: aggregate/limit on the cluster, collect the small result.

**Executor**: one task’s slice is too big — skew, too few shuffle partitions, huge broadcast, `coalesce` to a handful of giant partitions. Fix: Spark UI → Stages → tasks sorted by input / shuffle read. Fix **data shape** before raising memory.

## Broadcast risk

BHJ of a **tiny** dim is the cheap path. Disabling broadcast (`autoBroadcastJoinThreshold=-1`) on a large fact ⋈ small dim forces SMJ: shuffle + sort of the fact, which on a 2g worker can spill or OOM. That is “not broadcasting when you should”.

The opposite bug is broadcasting a large side.

## Failures that are not memory

`raise_error(...)` / `USER_RAISED_EXCEPTION` fails the **task** (and usually the job). It is a control-flow bug in the query, not a cluster outage.

If the product needs to **quarantine** bad rows (e.g. a country that a “policy backend” cannot handle): **filter** those rows to a reject path and write accepted rows. Do not evaluate `raise_error` on every matching row inside the write plan.

`spark.task.maxFailures` is **static** in Spark 4; this lab often fails fast. Lineage retries will not save a deterministic `raise_error`.

## Tungsten and UDFs

Built-in `pyspark.sql.functions` stay in the JVM (WholeStageCodegen).

Python `@udf` → `BatchEvalPython`, row-by-row pickle, **5–10×** slower, breaks codegen.

`@pandas_udf` → `ArrowEvalPython`, Arrow batches, still not fused, but far cheaper than row UDFs. Executors must have pandas/pyarrow (this repo’s worker image includes them).

Preference: SQL/built-in → Pandas UDF → Python UDF last and only on already-filtered data.

## Checklist

1. Spark UI Executors: who died?
2. Stages → outlier task by size/duration.
3. Plan: BHJ vs SMJ, `raise_error`, `BatchEvalPython`.
4. Fix operators/keys/filters; then memory configs.
