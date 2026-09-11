---
name: spark-debugging
description: Debug failed or pathological Apache Spark and PySpark applications from Spark UI, logs, and the physical plan. Use for task exceptions, USER_RAISED_EXCEPTION, executor loss, driver vs executor OOM, spill vs crash, fetch failures, Python worker deaths, and retries that hide the first error.
---

# Spark debugging

Find the **first** error that explains the rest. Later fetch-failed, timeout, and “executor lost” lines are usually debris. Configuration is intent. Task metrics, plan nodes, and logs are behavior.

## Collect evidence

```bash
export SPARK_UI_URL="http://localhost:4040"    # or History: http://localhost:18080
python3 scripts/spark_ui_snapshot.py snapshot --app-id <application-id> > /tmp/spark-debug.json
```

Same REST as the live SQL/Jobs/Stages tabs. If URL is unknown, probe `:4040`, `:18080`, then the Databricks Spark UI URL for that run. Auth: `SPARK_UI_AUTHORIZATION` / `SPARK_HISTORY_*`. TLS stays on.

REST does **not** include driver logs or container exit codes. Read `spark.master` and `spark.submit.deployMode` from `environment.sparkProperties`, then open the driver log and the first dead executor (Databricks event log, `kubectl logs --previous`, `yarn logs`). A driver crash can show **zero** failed Spark jobs.

Failed-task sample:

```bash
jq '[.failedStages[].tasks[]? | select(.errorMessage != null) | {stage: .stageId, index, attempt: .attemptNumber, host, executorId, err: .errorMessage[0:240]}]' /tmp/spark-debug.json
```

Quantile arrays are `[min, median, p95, p99, max]`.

## Classify the failure

Walk this list. Stop when one cause explains the chain.

1. **Deterministic code or SQL.** Same partition index, same exception, every attempt: `USER_RAISED_EXCEPTION`, `raise_error(...)`, Python `raise`, a poison record. Retries will not save it. If the business needs to quarantine rows, filter them to a reject output and write the rest — do not plant an error expression in the write plan for every matching row.

2. **Executor OOM, usually one task.** Inactive executors with OOM / exit 137. Then check the dying stage: max input or shuffle-read ≫ median → **skew or a huge build**, not “the cluster is undersized”. Broadcast hash tables sit in storage memory and **cannot spill**. Fix keys/strategy before raising `spark.executor.memory`.

3. **Spill, not a crash.** Stage SUCCEEDED with memory/disk spill. Execution memory filled; Spark wrote sort/hash files and continued. That is a size/partition/skew tuning problem, not an OOM. Do not treat spill counters as a failed job.

4. **Driver death.** No failed jobs, or heartbeats from executors while the app is gone. `collect` / `toPandas` of a large frame, collecting a too-large broadcast, or metadata blow-up from extreme partition counts. Aggregate on the cluster; sample with `take`/`limit`.

5. **Python worker.** Errors mention Python worker; plan has `BatchEvalPython` / `ArrowEvalPython`. Look at executor stderr. `spark.executor.pyspark.memory` is off-heap relative to the JVM. Missing pandas/pyarrow on **executors** fails Pandas UDFs even if the driver imported them.

6. **Fetch failed / executor lost (secondary).** The message names a shuffle block and an executor. That executor already died — diagnose *that* death (OOM, preemption, disk). Raising network timeouts buries the cause.

7. **One bad host vs one bad partition.** Group failed tasks by `host` and by `index`. All one host → infra (disk, preemption, bad node). All one partition, many hosts → data or code. Mix of hosts with later SUCCESS on retry → flaky infra.

8. **Timeouts and speculation.** Heartbeat/RPC timeouts follow GC or a stuck fat task. Speculation duplicates a straggler; if the partition is genuinely huge, the duplicate is huge too. Spark 4 speculation settings are often **static** at session start. Accumulators re-add on retry — never use them for money or exact counts.

`spark.task.maxFailures` is frequently static in Spark 4. A deterministic `raise_error` will burn every attempt.

## After it stays up

If the job now runs but is still wrong or still huge, switch to performance tuning (plan, shuffle, join strategy). Debugging stops at a stable, explained failure or a confirmed infra flake.

## Report

Confirmed vs hypothesis, first error (message, partition, executor, time), chain of fallout, smallest fix or reproduction, what evidence is still missing. Do not change production settings without approval.
