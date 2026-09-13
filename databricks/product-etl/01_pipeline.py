# Databricks notebook source
# MAGIC %md
# MAGIC # Daily USD KPIs
# MAGIC
# MAGIC Load a working transactions table and a small FX lookup, then publish daily USD KPIs.
# MAGIC
# MAGIC If a run is slow or expensive, use this cluster's Spark UI and the physical plan — wall time alone does not show join strategy, shuffle, or scan shape.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup

# COMMAND ----------

import time

from pyspark.sql import functions as F

dbutils.widgets.text(
    "source_txn",
    "hive_metastore.spark_tuning_test.transactions",
)
dbutils.widgets.text(
    "schema",
    "hive_metastore.spark_tuning_work",
)

SOURCE_TXN = dbutils.widgets.get("source_txn").strip()
SCHEMA = dbutils.widgets.get("schema").strip()

REQUIRED_COLS = ["transaction_description", "category", "country", "currency"]
BUSINESS_START = "2024-01-01"
BUSINESS_DAYS = 120
FACT_MIN_ROWS = 80000
STORE_COUNT = 25
FX_VENDORS = [
    "bloomberg",
    "reuters",
    "ecb_ref",
    "internal_ops",
    "morningstar",
    "refinitiv",
]


def _looks_like_table(name):
    """catalog.schema.table (or schema.table) vs a parquet path."""
    n = (name or "").strip()
    if not n or "/" in n or n.startswith("dbfs:") or "://" in n:
        return False
    if n.lower().endswith(".parquet"):
        return False
    parts = n.split(".")
    return 2 <= len(parts) <= 3 and all(p.isidentifier() for p in parts)


def _repeat_rows(df, copies, copy_col="_copy"):
    copies = int(copies)
    if copies <= 1:
        return df.withColumn(copy_col, F.lit(0))
    return df.crossJoin(spark.range(copies).withColumnRenamed("id", copy_col))


def _feed_payload(*parts):
    seed = F.concat_ws("|", *[F.coalesce(c.cast("string"), F.lit("")) for c in parts])
    chunks = [F.sha2(F.concat(seed, F.lit("#%d" % i)), 256) for i in range(48)]
    return F.concat(*chunks)


if not SOURCE_TXN:
    raise ValueError("source_txn widget is empty")
if not SCHEMA:
    raise ValueError("schema widget is empty")

spark.sql("CREATE SCHEMA IF NOT EXISTS {0}".format(SCHEMA))

TXN_TABLE = "{0}.transactions".format(SCHEMA)
if SOURCE_TXN.lower() == TXN_TABLE.lower():
    TXN_TABLE = "{0}.txn_working".format(SCHEMA)
FX_TABLE = "{0}.fx_rates".format(SCHEMA)
KPI_TABLE = "{0}.daily_usd_kpi".format(SCHEMA)

print("spark.version:", spark.version)
print("applicationId:", spark.sparkContext.applicationId)
print("source_txn:", SOURCE_TXN)
print("schema:", SCHEMA)
print("transactions:", TXN_TABLE)
print("fx_rates:", FX_TABLE)
print("daily_usd_kpi:", KPI_TABLE)
print("spark.sql.adaptive.enabled:", spark.conf.get("spark.sql.adaptive.enabled"))
print("spark.sql.shuffle.partitions:", spark.conf.get("spark.sql.shuffle.partitions"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Working tables
# MAGIC
# MAGIC Read the source extract. Persist a transactions table (ingest channel is `source_system`) and a dated FX lookup from the usual vendor feeds, including the raw payload.

# COMMAND ----------

if _looks_like_table(SOURCE_TXN):
    print("reading source as table:", SOURCE_TXN)
    src = spark.table(SOURCE_TXN)
else:
    print("reading source as parquet:", SOURCE_TXN)
    src = spark.read.parquet(SOURCE_TXN)

missing = [c for c in REQUIRED_COLS if c not in src.columns]
if missing:
    raise ValueError(
        "{0} missing columns {1}; have {2}".format(SOURCE_TXN, missing, src.columns)
    )

src_rows = src.count()
print("source rows:", src_rows)
if src_rows <= 0:
    raise ValueError("{0} has no rows".format(SOURCE_TXN))

fact_copies = 1
if src_rows < FACT_MIN_ROWS:
    fact_copies = (FACT_MIN_ROWS + src_rows - 1) // src_rows

other_store = F.concat(
    F.lit("ST-"),
    F.lpad(
        (F.floor(F.rand(102) * (STORE_COUNT - 1)) + F.lit(2)).cast("int").cast("string"),
        4,
        "0",
    ),
)

fact = (
    _repeat_rows(src, fact_copies)
    .withColumn(
        "txn_id",
        F.concat(F.lit("TXN-"), F.monotonically_increasing_id().cast("string")),
    )
    .withColumn(
        "store_id",
        F.when(F.rand(101) < 0.96, F.lit("ST-0001")).otherwise(other_store),
    )
    .withColumn(
        "business_date",
        F.date_add(
            F.lit(BUSINESS_START).cast("date"),
            F.floor(F.rand(103) * BUSINESS_DAYS).cast("int"),
        ),
    )
    .withColumn("amount", (F.rand(104) * 245.0 + F.lit(5.0)).cast("double"))
    .withColumn("source_system", F.lit("core_batch"))
    .drop("_copy")
)

fact_cols = [
    "txn_id",
    "store_id",
    "business_date",
    "amount",
    "source_system",
] + list(REQUIRED_COLS)
for c in src.columns:
    if c not in fact_cols:
        fact_cols.append(c)
fact = fact.select(*fact_cols)

spark.sql("DROP TABLE IF EXISTS {0}".format(TXN_TABLE))
(
    fact.write.mode("overwrite")
    .option("overwriteSchema", "true")
    .option("maxRecordsPerFile", 400)
    .partitionBy("source_system")
    .saveAsTable(TXN_TABLE)
)
print("wrote", TXN_TABLE, "rows:", spark.table(TXN_TABLE).count())

base_rates = spark.createDataFrame(
    [
        ("USD", 1.0),
        ("GBP", 1.27),
        ("CAD", 0.74),
        ("AUD", 0.66),
        ("INR", 0.012),
        ("EUR", 1.08),
        ("JPY", 0.0067),
        ("MXN", 0.058),
    ],
    ["currency", "base_rate"],
)
currencies = (
    spark.table(TXN_TABLE)
    .select("currency")
    .distinct()
    .union(base_rates.select("currency"))
    .distinct()
)
rate_dates = spark.range(BUSINESS_DAYS).select(
    F.date_add(F.lit(BUSINESS_START).cast("date"), F.col("id").cast("int")).alias(
        "rate_date"
    )
)
vendors = spark.createDataFrame([(v,) for v in FX_VENDORS], ["vendor"])

fx_rates = (
    currencies.crossJoin(rate_dates)
    .crossJoin(vendors)
    .join(base_rates, "currency", "left")
    .withColumn("base_rate", F.coalesce(F.col("base_rate"), F.lit(1.0)))
    .withColumn(
        "usd_rate",
        F.when(F.col("currency") == "USD", F.lit(1.0)).otherwise(
            (
                F.col("base_rate")
                * (
                    F.lit(1.0)
                    + (F.rand(201) - F.lit(0.5)) * F.lit(0.03)
                    + (F.hash(F.col("vendor")) % 7) * F.lit(0.0004)
                )
            ).cast("double")
        ),
    )
    .withColumn(
        "feed_payload",
        _feed_payload(
            F.col("currency"),
            F.col("rate_date"),
            F.col("vendor"),
            F.col("usd_rate"),
        ),
    )
    .select("currency", "rate_date", "usd_rate", "vendor", "feed_payload")
)

spark.sql("DROP TABLE IF EXISTS {0}".format(FX_TABLE))
(
    fx_rates.write.mode("overwrite")
    .option("overwriteSchema", "true")
    .option("compression", "uncompressed")
    .saveAsTable(FX_TABLE)
)
print("wrote", FX_TABLE, "rows:", spark.table(FX_TABLE).count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Daily USD KPIs
# MAGIC
# MAGIC USA activity, converted with FX by business date, rolled up by store.

# COMMAND ----------

spark.sparkContext.setJobGroup("daily_usd_kpi", "daily_usd_kpi")

t0 = time.perf_counter()

daily_usd = spark.sql(
    """
    SELECT
      t.store_id,
      t.business_date,
      t.currency,
      count(*) AS txn_count,
      sum(t.amount * f.usd_rate) AS usd_amount
    FROM {txn} t
    JOIN {fx} f
      ON t.currency = f.currency AND t.business_date = f.rate_date
    WHERE t.country = 'USA'
    GROUP BY t.store_id, t.business_date, t.currency
    """.format(txn=TXN_TABLE, fx=FX_TABLE)
)

daily_usd.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    KPI_TABLE
)

kpi_rows = spark.table(KPI_TABLE).count()
kpi_wall = round(time.perf_counter() - t0, 3)

print("daily_usd_kpi wall_time_sec:", kpi_wall)
print("daily_usd_kpi row_count:", kpi_rows)
print("applicationId:", spark.sparkContext.applicationId)
print("executed plan:")
print(daily_usd._jdf.queryExecution().executedPlan())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run summary
# MAGIC
# MAGIC Open **Compute → this cluster → Spark UI** for SQL, jobs, stages, and the physical plan. Use the cluster that ran this notebook — not `localhost`.

# COMMAND ----------

print("applicationId:", spark.sparkContext.applicationId)
print("daily_usd_kpi wall_time_sec:", kpi_wall, "row_count:", kpi_rows)
print("tables:")
spark.sql("SHOW TABLES IN {0}".format(SCHEMA)).show(truncate=False)
print(
    "Spark UI: Compute → this cluster → Spark UI "
    "(applicationId={0}). Do not use localhost.".format(
        spark.sparkContext.applicationId
    )
)
