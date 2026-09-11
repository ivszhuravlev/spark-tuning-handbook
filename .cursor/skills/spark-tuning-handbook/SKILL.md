---
name: spark-tuning-handbook
description: Router for this handbook's Spark internals skills. Use when diagnosing slow or failing Spark/PySpark jobs, reading Spark UI or physical plans, running skill-tests, or applying notebooks 01-05 (jobs/stages/tasks, Catalyst, shuffle, joins, skew, memory, AQE, failures) on the local Standalone cluster.
---

# Spark tuning handbook (router)

This repository is a Spark 4.0.2 internals course on a **local Standalone cluster** (2 workers, 2 cores / 2g each). Teach and diagnose the way the notebooks do: **plan + Spark UI first**, config knobs last.

This cluster is studied with **AQE off** unless the task is specifically about AQE (`spark.sql.adaptive.enabled=false`). Default demo shuffle partitions: `spark.sql.shuffle.partitions=8`.

## Load the matching skill

| Symptom or question | Skill | Notebook |
| --- | --- | --- |
| Jobs, stages, tasks, narrow vs wide, lazy eval, client vs cluster, too many tasks | `spark-architecture-execution` | 01 |
| `explain()`, Catalyst stages, predicate pushdown, column pruning, Exchange, BHJ vs SMJ in the plan, CBO vs heuristics | `spark-catalyst-planning` | 02 |
| Shuffle, spill, join strategy, skew, `repartition` vs `coalesce`, partition pruning | `spark-shuffle-joins` | 03 |
| Driver vs executor OOM, UMM, spill vs crash, Python UDF vs built-in vs Pandas UDF | `spark-memory-troubleshooting` | 04 |
| AQE, broadcast variables, accumulators, DRA, speculation, lineage / checkpoint | `spark-aqe-operations` | 05 |

Read the matching `SKILL.md` before changing job code. For a mixed failure (slow + wrong join + a failed task), load **architecture**, **shuffle-joins**, and **memory** together.

## How to diagnose (always)

1. Run the job. Note wall time, success/fail, row counts.
2. Spark UI `http://localhost:4040`: Jobs → Stages → task count, shuffle read/write, failed tasks, duration spread.
3. Physical plan (`explain()` / SQL tab): `Exchange`, `BroadcastHashJoin` vs `SortMergeJoin`, `FileScan` pushed filters, `BatchEvalPython`, `raise_error`.
4. Read the job source. Match operators to the plan (explode/repartition/join keys/conf overrides).
5. Fix **data shape and operators** first (unnecessary shuffle, join key, broadcast of a truly small side, row explosion, failing the whole stage on a reject). Then re-run and compare UI metrics.

Do not raise executor memory or turn AQE on as the first move on this lab cluster.

## Skill-test eval

`skill-tests/` is the eval harness for these skills, not a substitute for them.

- Assignment: `skill-tests/TASK.md` (no solution write-up in git).
- Run: `docker compose exec jupyter python /skill-tests/launch.py` (driver must be the Jupyter container on Mac/Linux Docker).
- UI: http://localhost:4040 while the session is alive.
- Fix `skill-tests/workloads/*.py`. Re-run until jobs complete, task/shuffle/join shape is healthy, and nothing fails unexpectedly.

Do not search the repo for answer keys. Diagnose from code, plan, and UI using the skills above.

## Cluster notes

- Mac/Linux: `docker compose up --build -d`. Jupyter http://localhost:8888. Master http://localhost:8080.
- Data: `data/transaction_cat.parquet` and `data/taxi/*.parquet`. Samples: `docker compose exec jupyter python /scripts/prepare_local_data.py`.
- Do not attach a Mac-native PySpark driver to Compose workers. Executors must RPC back to `spark.driver.host=spark-jupyter`.
