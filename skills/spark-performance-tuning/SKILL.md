---
name: spark-performance-tuning
description: Performance-tune Apache Spark and PySpark jobs from the executed physical plan and Spark UI metrics. Use when a job is too slow or too expensive and the fix should be operators, join strategy, shuffle shape, or partitioning — not a cluster resize. Covers Exchange, BroadcastHashJoin vs SortMergeJoin, skew, over-partitioning, row fan-out, predicate pushdown, and Python UDF cost.
---

# Spark performance tuning

Tune from **runtime evidence**, then code. Wall-clock without a plan is not a diagnosis. Adding workers or memory is the last move, not the first.

Spark executes **jobs → stages → tasks**. An action submits a job. A shuffle (`Exchange`) opens a new stage. One partition in that stage is one task. If you cannot name the expensive stage and why it shuffled, you are not tuning yet.

## Where to look

Use the Spark UI (or equivalent query profile) of **this run**, not a guess from source. Same tabs everywhere the driver UI is exposed: standalone, YARN, Kubernetes, EMR, Databricks job/cluster, History Server.

| Tab | Read |
| --- | --- |
| Jobs | One action ≈ one job. Duration, failed jobs. |
| Stages | Task count, shuffle read/write, spill, duration. Open the longest stage. |
| Stage → Tasks | Duration / shuffle read / input **min vs median vs max**. Max ≫ median is skew. |
| SQL | Final DAG. `Exchange`, `BroadcastHashJoin` vs `SortMergeJoin`, `FileScan` (pushed filters, read schema), `BatchEvalPython`. Prefer `isFinalPlan=true` if AQE ran. |
| Executors | Lost executors, GC time, shuffle metrics. |

SQL warehouses often show the same stories as a **query profile** (scans, joins, shuffles, rows) instead of the classic Spark UI.

If you cannot open UI, ask for the Spark UI / History / query-profile URL or a screenshot of Stages + SQL. Do not invent metrics.

## What “fast” looks like

- Task count on a stage is on the order of **cores**, not thousands, unless the data really needs it.
- Median task time close to max (no single partition owning the stage).
- Join with a small dimension is `BroadcastHashJoin`, not `SortMergeJoin` plus two Exchanges.
- Shuffle bytes are justified by the **keys you actually need**, not by a dummy redistribute.
- Scans show pushed filters and a narrow read schema.
- No `BatchEvalPython` on the hot path if a built-in expression exists.

## Tune in this order

1. **Remove invented work.** `explode` / `array_repeat` / unrestricted joins that multiply rows *before* an aggregate or shuffle. If the result grain is the original table, the fan-out is a bug. Compare scan rows to rows into the first `Exchange`.

2. **Fix join grain.** Output rows ≫ both inputs → many-to-many (join key too coarse). Join the key that matches the business grain, or pre-aggregate. This beats every later trick.

3. **Pick join strategy from observed size, not from table names.**
   - Tiny build side + `SortMergeJoin` → broadcast it (`broadcast(df)`), or stop forcing `autoBroadcastJoinThreshold=-1`.
   - In-memory lookups (`createDataFrame`) often have **unknown size** → planner chooses SMJ; an explicit broadcast is the fix.
   - Two large facts → SMJ (or SHJ) is correct. Do not broadcast tens of gigabytes.
   - Broadcast lives in **storage** memory and **cannot spill**; it fits or it OOMs.

4. **Kill pointless shuffles.** `repartition(N)` with N in the hundreds/thousands on small data is a task storm. `repartition` always shuffles; `coalesce` does not. Keep `repartition(n, key)` for key alignment only. AQE coalescing (`AQEShuffleRead`) can merge tiny partitions **after** you already paid to create them — it does not make a 2000-way repartition free.

5. **Skew on a shuffled join or agg.** Max shuffle-read or runtime many times the median → hot key. Prefer a real key or broadcast the small side. Salt only when both sides are large. Speculation copies the fat partition; it does not fix skew. AQE skew split only applies to **SMJ after shuffle**.

6. **Shrink what you shuffle and sort.** Drop columns before the wide op. Partial aggregate before join when the logic allows. Spill with SUCCESS means execution memory filled — reduce state or raise partition count **after** skew is ruled out, then consider memory.

7. **Native expressions over Python.** `BatchEvalPython` is a codegen barrier. Pandas/Arrow UDFs are better; Spark SQL / built-in functions are best. Executors must have the Python packages you call.

8. **AQE last, and only for what it does.** Coalesce tiny shuffle parts, switch SMJ→BHJ when *runtime* size is small, split oversized SMJ partitions. It will not delete a useless explode, a wrong join key, or a Python UDF. Do not “enable AQE” as a substitute for reading the plan.

9. **Cluster resize last.** More workers help when tasks are busy, not skewed, and parallelism is actually capped by cores. More heap helps a uniformly fat partition, not a 100× hot key.

## Report

Highest-impact change, plan node + stage id, numbers (rows, shuffle bytes, tasks, median vs max), why Spark did not already do it, correctness risk (join keys, duplicates, ordering). Do not apply production conf or expensive reruns without approval.
