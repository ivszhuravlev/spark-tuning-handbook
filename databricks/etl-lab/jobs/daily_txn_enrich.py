"""Nightly enrich: tokenize, redistribute, then country rollup."""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, explode, array_repeat, lit, length, avg, count


def _read_txn(spark, txn_path):
    if txn_path.startswith("dbfs:") or txn_path.startswith("/") or ".parquet" in txn_path:
        return spark.read.parquet(txn_path)
    return spark.table(txn_path)


def _write_out(df, out_dir, name):
    if "/" in out_dir or out_dir.startswith("dbfs:"):
        df.write.mode("overwrite").parquet(f"{out_dir.rstrip('/')}/{name}")
        return
    df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{out_dir}.{name}")


def run(spark: SparkSession, txn_path: str, out_dir: str) -> int:
    spark.sparkContext.setJobGroup("daily_txn_enrich", "daily_txn_enrich")
    df = _read_txn(spark, txn_path)
    fanned = df.withColumn("_dup", explode(array_repeat(lit(1), 12))).drop("_dup")
    result = (
        fanned.withColumn("desc_len", length(col("transaction_description")))
        .repartition(2000)
        .groupBy("country")
        .agg(count("*").alias("txn_count"), avg("desc_len").alias("avg_desc_len"))
    )
    _write_out(result, out_dir, "daily_txn_enrich")
    return result.count()
