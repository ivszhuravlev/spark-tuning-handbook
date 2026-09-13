# Daily USD KPIs

One Databricks notebook: a transactions table plus a small FX lookup become a daily USD KPI table. Run it on a **Databricks cluster**. After the KPI write, open that cluster’s Spark UI / SQL query profile — not `localhost`.

## Layout

| Path | What it is |
| --- | --- |
| `01_pipeline.py` | Load working tables, then the KPI query. |

## How to run

1. Attach `01_pipeline.py` to a Databricks cluster and run it to completion.
2. Use the cluster Spark UI (Jobs / Stages / SQL) for that application.

## Widgets

| Widget | Default | Purpose |
| --- | --- | --- |
| `source_txn` | `hive_metastore.spark_tuning_test.transactions` | Source extract (table or parquet). Expected columns include `transaction_description`, `category`, `country`, `currency`. |
| `schema` | `hive_metastore.spark_tuning_work` | Schema for the working tables and the KPI output. |

Set the widgets before you run if your workspace uses different catalog or schema names. The notebook prints Spark version and application id.

Tables it writes under `schema`:

- `transactions` — working copy of the extract (`txn_working` if `source_txn` is already that name)
- `fx_rates` — dated FX lookup
- `daily_usd_kpi` — USA activity converted to USD and rolled up by store and day

The KPI query is ordinary SQL: join transactions to FX on currency and business date, filter `country = 'USA'`, `GROUP BY` store / date / currency.

## Assistant

Attach the notebook and the Spark UI (or SQL query profile) from the KPI run on the cluster. If the job is slow, the assistant should use Spark UI / the physical plan.
