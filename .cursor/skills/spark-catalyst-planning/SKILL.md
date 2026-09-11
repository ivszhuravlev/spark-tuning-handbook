---
name: spark-catalyst-planning
description: Catalyst parsed/analyzed/optimized/physical plans, predicate pushdown, column pruning, Exchange, and join-strategy selection (BHJ vs SMJ). Use when reading explain() or the SQL tab, comparing CBO vs heuristics, or a small lookup is still SortMergeJoin (notebook 02).
---

# Catalyst optimizer and query planning

Source of truth: `notebooks/02_catalyst_optimizer_and_query_planning.ipynb`.

You write DataFrame/SQL → logical plan → Catalyst rewrites → **physical plan** (scans, exchanges, hashes, sorts).

## Four plan stages

1. **Parsed** — what you typed; names may be unresolved.
2. **Analyzed** — columns/types resolved. `AnalysisException` happens here (including ambiguous columns after a join).
3. **Optimized** — rule-based (RBO), no stats required: predicate pushdown, column pruning, constant folding, `isnotnull` on inner-join keys.
4. **Physical** — how it runs: FileScan, BroadcastHashJoin vs SortMergeJoin, `Exchange hashpartitioning`, WholeStageCodegen (`*` prefix).

`explain(extended=True)` dumps all four. For performance, read **physical** and, after an action, the SQL tab executed plan.

## What to look for (fast)

1. **FileScan** — pushed filters, read schema (unused columns still being read = pruning failed).
2. **Exchange** — shuffle. Each Exchange is a stage boundary.
3. **Join operator** — `BroadcastHashJoin` / `BroadcastNestedLoopJoin` vs `SortMergeJoin` vs `ShuffledHashJoin`.
4. **Sort** — SMJ and global `orderBy`.
5. **WholeStageCodegen** — `*` on operators. A Python UDF inserts `BatchEvalPython` and breaks fusion (see `spark-memory-troubleshooting`).

Expensive tells: Exchange + Sort + a full scan with no pushed filter.

## Join strategy in the planner

Spark picks a physical join from size estimates + config, not from “join looks small in Python”.

- **Broadcast Hash Join** — one side under `spark.sql.autoBroadcastJoinThreshold` (default 10 MB) **or** `broadcast(small_df)`. Small side collected on the driver, hashed on every executor. No shuffle of the large side for the join.
- **Sort-Merge Join** — both sides shuffled and sorted. Default scalable path when broadcast is off or sizes are unknown.
- A `createDataFrame` / `LogicalRDD` often has **unknown size**, so the planner picks SMJ even for five rows. `broadcast()` or a real table with `ANALYZE TABLE` stats fixes that. Relation-size broadcast is **not** the same as CBO join reordering (`spark.sql.cbo.enabled` defaults to false in Spark 4).

`spark.sql.autoBroadcastJoinThreshold=-1` **forces** SMJ/SHJ. If a job sets that around a tiny dimension, that is the bug.

## CBO vs RBO

RBO always runs. CBO needs table/column stats (`ANALYZE TABLE … COMPUTE STATISTICS`). Stale stats can be worse than none. On this lab, prefer an explicit `broadcast()` when one side is obviously a lookup.

## Ambiguous columns

After `join` on a key that exists on both sides, `groupBy("country")` (or any unqualified name) can fail with `AMBIGUOUS_REFERENCE`. Project/rename so each remaining column has one origin.
