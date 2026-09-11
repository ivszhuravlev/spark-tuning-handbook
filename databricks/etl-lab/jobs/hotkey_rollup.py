"""Market-mix rollup. Bucket keys, join to the mix map, aggregate."""

from pyspark.sql import SparkSession
from pyspark.sql.functions import avg, col, count, length, lit, rand, when


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
    spark.sparkContext.setJobGroup("hotkey_rollup", "hotkey_rollup")
    prev_thr = spark.conf.get("spark.sql.autoBroadcastJoinThreshold")
    prev_parts = spark.conf.get("spark.sql.shuffle.partitions")
    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")
    spark.conf.set("spark.sql.shuffle.partitions", "8")
    try:
        txn = _read_txn(spark, txn_path)
        left = txn.withColumn(
            "join_key",
            when(rand(seed=1) < 0.98, lit("HOT")).otherwise(col("category")),
        )
        mix_keys = [("HOT", "standard_book")] + [
            (c, "long_tail")
            for c in (
                "groceries",
                "restaurants",
                "transport",
                "utilities",
                "entertainment",
                "health",
                "shopping",
                "travel",
                "education",
                "other",
                "Income",
                "Transportation",
                "Shopping & Retail",
                "Utilities & Services",
                "Financial Services",
            )
        ]
        right = spark.createDataFrame(mix_keys, ["join_key", "book"])
        joined = left.join(right, "join_key")
        result = joined.groupBy("join_key", "book").agg(
            count("*").alias("txn_count"),
            avg(length(col("transaction_description"))).alias("avg_desc_len"),
        )
        _write_out(result, out_dir, "hotkey_rollup")
        return result.count()
    finally:
        spark.conf.set("spark.sql.autoBroadcastJoinThreshold", prev_thr)
        spark.conf.set("spark.sql.shuffle.partitions", prev_parts)
