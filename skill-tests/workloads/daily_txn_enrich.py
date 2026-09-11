"""Nightly enrich: tokenize, redistribute, then country rollup."""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, explode, array_repeat, lit, length, avg, count


def run(spark: SparkSession, txn_path: str, out_dir: str) -> int:
    spark.sparkContext.setJobGroup("daily_txn_enrich", "daily_txn_enrich")
    df = spark.read.parquet(txn_path)
    fanned = df.withColumn("_dup", explode(array_repeat(lit(1), 12))).drop("_dup")
    result = (
        fanned.withColumn("desc_len", length(col("transaction_description")))
        .repartition(2000)
        .groupBy("country")
        .agg(count("*").alias("txn_count"), avg("desc_len").alias("avg_desc_len"))
    )
    result.write.mode("overwrite").parquet(f"{out_dir}/daily_txn_enrich")
    return result.count()
