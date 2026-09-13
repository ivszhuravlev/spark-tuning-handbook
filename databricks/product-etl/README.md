# Product ETL (gold from silver)

Databricks notebooks that build gold KPIs from silver tables. Run them on a **Databricks cluster**. After a gold run, open that cluster’s Spark UI / SQL query profile for the application — not `localhost`.

## Layout

| Path | Who runs it |
| --- | --- |
| `_staff/00_build_silver.py` | Staff only. Builds the silver tables the gold notebook reads. |
| `01_gold_pipeline.py` | Gold batch: widgets, SQL gold tables, timings, row counts. |

`_staff/` is not part of the gold notebook. Do not ship it to an assistant.

## How to run

1. Attach `_staff/00_build_silver.py` to a Databricks cluster and run it to completion. It reads `source_txn` and writes silver tables under `silver_schema`.
2. Attach `01_gold_pipeline.py` to the same (or a compatible) cluster and run it. It reads silver and writes gold under `gold_schema`.
3. Use the cluster Spark UI (Jobs / Stages / SQL) for the gold application.

If silver is already built for those widget values, you can re-run gold alone.

## Widgets

Both notebooks use these text widgets:

| Widget | Default | Purpose |
| --- | --- | --- |
| `source_txn` | `hive_metastore.spark_tuning_test.transactions` | Source transactions (table or parquet). Expected columns include `transaction_description`, `category`, `country`, `currency`. |
| `silver_schema` | `hive_metastore.spark_tuning_silver` | Schema that holds silver tables. |
| `gold_schema` | `hive_metastore.spark_tuning_gold` | Schema for gold output. |

Set the widgets before you run if your workspace uses different catalog or schema names. The gold notebook `USE`s these schemas and prints Spark version and application id.

Silver tables the gold notebook reads (under `silver_schema`): `txn_fact`, `dim_store`, `fx_daily`. Gold writes KPI tables under `gold_schema` (daily store-region KPIs, plus an optional country rollup).

## Assistant eval

Attach **only**:

1. `01_gold_pipeline.py`
2. The Spark UI (or SQL query profile) from that gold run on the cluster

Do **not** attach `_staff/` (including the silver builder). The gold notebook is a batch gold build from silver; if it is slow, the assistant should use Spark UI / the physical plan.
