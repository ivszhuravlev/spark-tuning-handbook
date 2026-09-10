"""Country overlap report: match books of record across two extracts."""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count


def run(spark: SparkSession, txn_path: str, out_dir: str) -> int:
    spark.sparkContext.setJobGroup("country_overlap", "country_overlap")
    prev = spark.conf.get("spark.sql.autoBroadcastJoinThreshold")
    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")
    try:
        txn = spark.read.parquet(txn_path)
        left = txn.select("country", "category", "currency").limit(12000)
        right = txn.select("country", "category").limit(12000)
        overlapped = left.join(right, "country")
        pair_count = overlapped.count()
        result = overlapped.groupBy("country").agg(count("*").alias("pair_count"))
        result.write.mode("overwrite").parquet(f"{out_dir}/country_overlap")
        return int(pair_count)
    finally:
        spark.conf.set("spark.sql.autoBroadcastJoinThreshold", prev)
