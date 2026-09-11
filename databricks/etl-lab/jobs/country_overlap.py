"""Country overlap report: match books of record across two extracts."""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count


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
    spark.sparkContext.setJobGroup("country_overlap", "country_overlap")
    prev = spark.conf.get("spark.sql.autoBroadcastJoinThreshold")
    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")
    try:
        txn = _read_txn(spark, txn_path)
        left = txn.select("country", "category", "currency").limit(12000)
        right = txn.select("country", "category").limit(12000)
        overlapped = left.join(right, "country")
        pair_count = overlapped.count()
        result = overlapped.groupBy("country").agg(count("*").alias("pair_count"))
        _write_out(result, out_dir, "country_overlap")
        return int(pair_count)
    finally:
        spark.conf.set("spark.sql.autoBroadcastJoinThreshold", prev)
