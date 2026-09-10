"""Market-mix rollup. Bucket keys, join to the mix map, aggregate."""

from pyspark.sql import SparkSession
from pyspark.sql.functions import avg, col, count, length, lit, rand, when


def run(spark: SparkSession, txn_path: str, out_dir: str) -> int:
    spark.sparkContext.setJobGroup("hotkey_rollup", "hotkey_rollup")
    prev_thr = spark.conf.get("spark.sql.autoBroadcastJoinThreshold")
    prev_parts = spark.conf.get("spark.sql.shuffle.partitions")
    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")
    spark.conf.set("spark.sql.shuffle.partitions", "8")
    try:
        txn = spark.read.parquet(txn_path)
        # Handbook 03 pattern: almost all rows share one join key.
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
        result.write.mode("overwrite").parquet(f"{out_dir}/hotkey_rollup")
        return result.count()
    finally:
        spark.conf.set("spark.sql.autoBroadcastJoinThreshold", prev_thr)
        spark.conf.set("spark.sql.shuffle.partitions", prev_parts)
