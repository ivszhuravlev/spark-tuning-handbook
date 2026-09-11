---
name: spark-architecture-execution
description: Spark Job → Stage → Task model, narrow vs wide transformations, lazy evaluation, and client vs cluster mode. Use when counting jobs/stages/tasks, explaining shuffle boundaries, too many tasks, or why an action triggered work on the handbook Standalone cluster (notebook 01).
---

# Architecture and execution model

Source of truth: `notebooks/01_architecture_and_execution_model.ipynb`. Spark UI: http://localhost:4040.

Keep AQE off while learning shapes: `spark.sql.adaptive.enabled=false`.

## Job → Stage → Task

When an **action** runs (`count`, `collect`, `show`, `write`, `save`, `take`, `foreach`):

Driver → DAGScheduler → **stages** (split at shuffle) → **tasks** (one per partition per stage) → executors on workers.

Rules:

- **1 action = 1 job** in the teaching model. Each `count` / `show` / `write.*` submits work. Cached reads and SQL planning can add extra jobs; still start from “this action created that job”.
- **Shuffle = stage boundary.** Wide ops (`groupBy`, `join`, `repartition`, `orderBy`, `distinct`) introduce a new stage.
- **1 partition = 1 task** in a stage.

Example: 8 partitions and one shuffle → **2 stages × 8 tasks**.

A stage with **hundreds or thousands of tasks** on this tiny cluster is almost always an explicit `repartition(N)` or `spark.sql.shuffle.partitions` far above the data size — not “Spark being thorough”.

## Narrow vs wide

**Narrow** (partition-local, no network): `filter`, `select`, `withColumn`. Several narrow ops pipeline in **one stage**.

**Wide** (shuffle): `groupBy`, `join`, `repartition`, `orderBy`, `distinct`. Expect shuffle write on the map stage and shuffle read on the reduce stage.

Multiple wide ops → multiple `Exchange`s → **N shuffles → N+1 stages**.

`explode` / `array_repeat` that duplicate rows **before** a wide op multiply shuffle bytes and downstream work. If the business result is a `groupBy` on the original grain, do not fan out rows first.

## Lazy evaluation

Transformations only append to the DAG. Nothing runs until an action. That is why Catalyst can push filters and fuse narrow ops.

If Spark UI shows no new job, you have not called an action yet.

## Client vs cluster mode

This handbook cluster is **client mode**: the driver is the Jupyter kernel (or the process that created the `SparkSession`). Kill the notebook, the app dies. Spark UI is on the driver host (port 4040).

**Cluster mode** (`spark-submit --deploy-mode cluster`): driver runs on a cluster node; used for production, not these notebooks.

On Mac Docker: the driver **must** be the `jupyter` container (`spark.driver.host=spark-jupyter`). A Mac-native `pyspark` cannot receive executor RPC.

## Spark UI checklist

- Jobs: count and duration per action.
- Stages: shuffle read/write, task count.
- Stage detail: task duration histogram. One fat task among many = skew (see `spark-shuffle-joins`).
- Shuffle Write = 0 on a “simple count of parquet” is expected (narrow scan). Shuffle Write >> input after a pointless `repartition` is a bug in the job, not in the cluster.
