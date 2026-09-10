# Skill tests

Jobs that violate the handbook on purpose (shuffle, join strategy, skew, partitioning) so another agent can diagnose them from **job code + Spark UI**. AQE is off, same as notebooks 01–03.

Planted-fault answers are **not in git**.

## Run

Cluster up, `data/transaction_cat.parquet` present:

```bash
export SPARK_MASTER=spark://localhost:7077
python skill-tests/launch.py
```

Spark UI: http://localhost:4040 while the session is alive (`SKILL_TEST_KEEP_UI=1` to keep it).

## Jobs

| Job group | Script | Handbook topic |
|---|---|---|
| `daily_txn_enrich` | `workloads/daily_txn_enrich.py` | extra shuffle / too many tasks (01, 03) |
| `fx_lookup_join` | `workloads/fx_lookup_join.py` | join strategy: tiny dim, no broadcast (03) |
| `hotkey_rollup` | `workloads/hotkey_rollup.py` | skew hot key, AQE off (03) |
| `country_overlap` | `workloads/country_overlap.py` | many-to-many join / row explosion (03) |
| `qc_reject` | `workloads/qc_reject.py` | failing stage (04) |

## Eval

Read the workload Python and Spark UI (jobs, stages, SQL plan). Do not expect an answer file in the clone.
