---
name: spark-performance-tuning
description: Performance-tune Apache Spark and PySpark jobs from the executed physical plan and Spark UI metrics. Use when a job is too slow or too expensive and the fix should be operators, join strategy, shuffle shape, or partitioning — not a cluster resize. Covers Exchange, BroadcastHashJoin vs SortMergeJoin, skew, over-partitioning, row fan-out, predicate pushdown, and Python UDF cost.
---

# Spark performance tuning

Tune from **runtime evidence**, then code. Wall-clock without a plan is not a diagnosis. Adding executors or memory is the last move, not the first.

Spark executes **jobs → stages → tasks**. An action submits a job. A shuffle (`Exchange`) opens a new stage. One partition in that stage is one task. If you cannot name the expensive stage and why it shuffled, you are not tuning yet.

## Collect evidence

Live driver UI and History Server share `/api/v1`:

```bash
export SPARK_UI_URL="http://localhost:4040"    # or History: http://localhost:18080
python3 scripts/spark_ui_snapshot.py apps
python3 scripts/spark_ui_snapshot.py snapshot --app-id <application-id> > /tmp/spark-tune.json
python3 scripts/spark_ui_snapshot.py sql --app-id <application-id> --execution-id <n> > /tmp/spark-plan.json
```

If the URL is unset, try `:4040`, then `:18080`, then the Spark UI link on the Databricks job/cluster, then event-log / history settings. Auth via `SPARK_UI_AUTHORIZATION` (or `SPARK_HISTORY_*`). Do not disable TLS. Do not ask for secrets in chat.

In `taskSummary`, quantile arrays are `[min, median, p95, p99, max]`. Read the **final** SQL plan (`isFinalPlan=true` when AQE ran). The initial plan is a guess.

## What “fast” looks like

- Task count on a stage is on the order of **cores**, not thousands, unless the data really needs it.
- Median task time close to max (no single partition owning the stage).
- Join with a small dimension is `BroadcastHashJoin`, not `SortMergeJoin` plus two Exchanges.
- Shuffle bytes are justified by the **keys you actually need**, not by a dummy redistribute.
- Scans show pushed filters and a narrow read schema.
- No `BatchEvalPython` on the hot path if a built-in expression exists.

## Tune in this order

1. **Remove invented work.** `explode` / `array_repeat` / unrestricted joins that multiply rows *before* an aggregate or shuffle. If the result grain is the original table, the fan-out is a bug. Check SQL node output rows vs scan rows.

2. **Fix join grain.** Output rows ≫ both inputs → many-to-many (join key too coarse). Join the key that matches the business grain, or pre-aggregate. This beats every later trick.

3. **Pick join strategy from observed size, not from table names.**
   - Tiny build side + `SortMergeJoin` → broadcast it (`broadcast(df)`), or stop forcing `autoBroadcastJoinThreshold=-1`.
   - In-memory lookups (`createDataFrame`) often have **unknown size** → planner chooses SMJ; an explicit broadcast is the fix.
   - Two large facts → SMJ (or SHJ) is correct. Do not broadcast tens of gigabytes.
   - Broadcast lives in **storage** memory and **cannot spill**; it fits or it OOMs.

4. **Kill pointless shuffles.** `repartition(N)` with N in the hundreds/thousands on small data is a task storm. `repartition` always shuffles; `coalesce` does not. Keep `repartition(n, key)` for key alignment only. AQE coalescing (`AQEShuffleRead`) can merge tiny partitions **after** you already paid to create them — it does not make a 2000-way repartition free.

5. **Skew on a shuffled join or agg.** Max shuffle-read or runtime many times the median → hot key. Prefer a real key or broadcast the small side. Salt only when both sides are large. Speculation copies the fat partition; it does not fix skew. AQE skew split only applies to **SMJ after shuffle**.

6. **Shrink what you shuffle and sort.** Drop columns before the wide op. Partial aggregate before join when the logic allows. Spill with SUCCESS means execution memory filled — reduce state or raise partition count **after** skew is ruled out, then consider memory.

7. **Native expressions over Python.** `BatchEvalPython` is a codegen barrier (row pickle). Pandas/Arrow UDFs are better; SQL/`pyspark.sql.functions` are best. Executors must have the Python packages you call.

8. **AQE last, and only for what it does.** Coalesce tiny shuffle parts, switch SMJ→BHJ when *runtime* size is small, split oversized SMJ partitions. It will not delete a useless explode, a wrong join key, or a Python UDF. This skill assumes you can read a static plan; do not “enable AQE” as a substitute for that.

9. **Cluster resize last.** More executors help when tasks are busy, not skewed, and parallelism is actually capped by cores. More heap helps a uniformly fat partition, not a 100× hot key.

## Report

Highest-impact change, plan node + stage id, numbers (rows, shuffle bytes, tasks, median vs max), why Spark did not already do it, correctness risk (join keys, duplicates, ordering). Do not apply production conf or expensive reruns without approval.
