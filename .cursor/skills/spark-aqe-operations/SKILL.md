---
name: spark-aqe-operations
description: Adaptive Query Execution, broadcast variables vs DataFrame broadcast joins, accumulators, dynamic allocation, speculative execution, and lineage/checkpoint. Use when AQE plan nodes, stragglers, task retries, or Spark 4 static configs are in play (notebook 05).
---

# AQE and operations

Source of truth: `notebooks/05_performance_tuning_and_operations.ipynb`.

This course **starts with AQE off** so Job/Stage/Exchange shapes stay deterministic. Enable AQE only when the question is AQE. The skill-test launcher sets `spark.sql.adaptive.enabled=false`.

## Adaptive Query Execution

AQE rewrites the plan **after shuffle stages** using real partition sizes.

1. **Partition coalescing** — many tiny post-shuffle partitions → `AQEShuffleRead` with fewer tasks. Demo: `shuffle.partitions=400` on a low-cardinality agg.
2. **Join strategy switch** — planned SMJ can become BHJ if a side is actually under the **adaptive** broadcast threshold (`spark.sql.adaptive.autoBroadcastJoinThreshold`), even when static `autoBroadcastJoinThreshold=-1`.
3. **Skew join** — split oversized SMJ shuffle partitions (`skewJoin.skewedPartitionThresholdInBytes`, `skewedPartitionFactor`). Plan may show `isSkewJoin=true`. **Requires SMJ** (both sides shuffled). If one side is broadcast, AQE has nothing to split.

Read AQE **after** an action: `AdaptiveSparkPlan isFinalPlan=true`. Before an action the plan is a prediction.

AQE does **not** fix Python UDF cost, wrong join keys, or row explosions with no shuffle.

On this lab, a healthy job is usually **correct operators + BHJ where the dim is tiny**, not “turn AQE on and hope”.

## Broadcast variables vs DataFrame broadcast

`sc.broadcast(value)` — one read-only copy **per executor** for RDD/UDF closures (lookup sets, models).

DataFrame `broadcast(df)` / auto-threshold — **join strategy**. Do not confuse the two.

## Accumulators

Tasks only add; driver reads. Retried or speculated tasks **add again**. Use for monitoring, never for money or row counts that must be exact.

## Dynamic resource allocation

Needs a shuffle service (or Spark 4 shuffle tracking) so released executors do not delete shuffle files. **Standalone Compose with two workers will not demonstrate DRA.** `spark.dynamicAllocation.*` is static — set on session start, not `spark.conf.set` in a notebook.

## Speculative execution

Straggler = task much slower than the stage median. `spark.speculation=true` launches a duplicate after `multiplier × median` (Spark 4 default multiplier **3**, quantile **0.9**). Winner wins; loser killed.

Does **not** help a task that genuinely has more data (skew). Duplicate that partition and you duplicate the skew.

Spark 4: `spark.speculation` is **static**.

## Fault tolerance

Lineage recomputes lost partitions. `spark.task.maxFailures` (default 4; often 1 here) is static in Spark 4.

Deterministic query errors (`raise_error`) fail every attempt. Filter/quarantine instead of signalling in the hot path.

Checkpoint truncates lineage (`sc.setCheckpointDir`, `rdd.checkpoint()` on the next action). Cache is fast and volatile; checkpoint is slower and durable. This lab’s Docker cluster cannot usefully kill an executor to demo stage recovery.
