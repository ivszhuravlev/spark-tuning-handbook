# Databricks notebook source
# MAGIC %md
# MAGIC # Gold store KPIs
# MAGIC
# MAGIC Production batch that publishes gold marts from silver: store-level USD KPIs and a country rollup.
# MAGIC
# MAGIC Silver inputs are the transaction fact, the current store dimension, and FX by business date. Gold is overwritten each run.
# MAGIC
# MAGIC If a run is slow or expensive, use this cluster's Spark UI and the physical plan — wall time alone does not show join strategy, shuffle, or scan shape.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup

# COMMAND ----------

import time

dbutils.widgets.text(
    "silver_schema",
    "hive_metastore.spark_tuning_silver",
)
dbutils.widgets.text(
    "gold_schema",
    "hive_metastore.spark_tuning_gold",
)

SILVER_SCHEMA = dbutils.widgets.get("silver_schema").strip()
GOLD_SCHEMA = dbutils.widgets.get("gold_schema").strip()

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {GOLD_SCHEMA}")

print("spark.version:", spark.version)
print("applicationId:", spark.sparkContext.applicationId)
print("silver_schema:", SILVER_SCHEMA)
print("gold_schema:", GOLD_SCHEMA)
print("spark.sql.adaptive.enabled:", spark.conf.get("spark.sql.adaptive.enabled"))
print("spark.sql.shuffle.partitions:", spark.conf.get("spark.sql.shuffle.partitions"))

spark.sql(f"SHOW TABLES IN {SILVER_SCHEMA}").show(truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Store KPIs (USD)
# MAGIC
# MAGIC Daily region × currency KPIs for USA activity. Amounts are converted with FX by business date and attributed to the current store dimension.

# COMMAND ----------

spark.sparkContext.setJobGroup("gold_store_kpis", "gold_store_kpis")

t0 = time.perf_counter()

# current store dimension; FX by business date
store_kpis = spark.sql(
    f"""
    SELECT
      s.region,
      t.business_date,
      t.currency,
      count(*) AS txn_count,
      sum(t.amount * f.usd_rate) AS usd_amount
    FROM {SILVER_SCHEMA}.txn_fact t
    JOIN {SILVER_SCHEMA}.dim_store s
      ON t.store_id = s.store_id AND s.is_current
    JOIN {SILVER_SCHEMA}.fx_daily f
      ON t.currency = f.currency AND t.business_date = f.rate_date
    WHERE t.country = 'USA'
    GROUP BY s.region, t.business_date, t.currency
    """
)

store_kpis.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    f"{GOLD_SCHEMA}.gold_store_kpis"
)

store_kpi_rows = spark.table(f"{GOLD_SCHEMA}.gold_store_kpis").count()
store_kpi_wall = round(time.perf_counter() - t0, 3)

print("gold_store_kpis wall_time_sec:", store_kpi_wall)
print("gold_store_kpis row_count:", store_kpi_rows)
print("applicationId:", spark.sparkContext.applicationId)
print("executed plan:")
print(store_kpis._jdf.queryExecution().executedPlan())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Country rollup
# MAGIC
# MAGIC Country-level activity from the transaction fact (local amounts, no FX).

# COMMAND ----------

spark.sparkContext.setJobGroup("gold_country_kpis", "gold_country_kpis")

t1 = time.perf_counter()

country_kpis = spark.sql(
    f"""
    SELECT
      t.country,
      count(*) AS txn_count,
      count(DISTINCT t.store_id) AS store_count,
      sum(t.amount) AS local_amount,
      min(t.business_date) AS min_business_date,
      max(t.business_date) AS max_business_date
    FROM {SILVER_SCHEMA}.txn_fact t
    GROUP BY t.country
    """
)

country_kpis.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    f"{GOLD_SCHEMA}.gold_country_kpis"
)

country_kpi_rows = spark.table(f"{GOLD_SCHEMA}.gold_country_kpis").count()
country_kpi_wall = round(time.perf_counter() - t1, 3)

print("gold_country_kpis wall_time_sec:", country_kpi_wall)
print("gold_country_kpis row_count:", country_kpi_rows)
print("applicationId:", spark.sparkContext.applicationId)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run summary
# MAGIC
# MAGIC Open **Compute → this cluster → Spark UI** for SQL, jobs, stages, and the physical plan. Use the cluster that ran this notebook — not `localhost`.

# COMMAND ----------

print("applicationId:", spark.sparkContext.applicationId)
print("gold_store_kpis wall_time_sec:", store_kpi_wall, "row_count:", store_kpi_rows)
print("gold_country_kpis wall_time_sec:", country_kpi_wall, "row_count:", country_kpi_rows)
print("total_wall_time_sec:", round(store_kpi_wall + country_kpi_wall, 3))
print("gold tables:")
spark.sql(f"SHOW TABLES IN {GOLD_SCHEMA}").show(truncate=False)
print(
    "Spark UI: Compute → this cluster → Spark UI "
    f"(applicationId={spark.sparkContext.applicationId}). Do not use localhost."
)
