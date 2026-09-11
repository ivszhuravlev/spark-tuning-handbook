"""Join the transaction stream to a static FX table, then roll up by currency."""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, explode, array_repeat, lit, count, avg, length


def run(spark: SparkSession, txn_path: str, out_dir: str) -> int:
    spark.sparkContext.setJobGroup("fx_lookup_join", "fx_lookup_join")
    prev_thr = spark.conf.get("spark.sql.autoBroadcastJoinThreshold")
    prev_smj = spark.conf.get("spark.sql.join.preferSortMergeJoin", "true")
    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")
    spark.conf.set("spark.sql.join.preferSortMergeJoin", "true")
    try:
        txn = spark.read.parquet(txn_path)
        facts = txn.withColumn("_dup", explode(array_repeat(lit(1), 8))).drop("_dup")
        fx = spark.createDataFrame(
            [
                ("USD", 1.0),
                ("GBP", 1.27),
                ("CAD", 0.74),
                ("AUD", 0.66),
                ("INR", 0.012),
            ],
            ["currency", "usd_rate"],
        )
        joined = facts.join(fx, "currency")
        result = joined.groupBy("currency").agg(
            count("*").alias("txn_count"),
            avg(length(col("transaction_description"))).alias("avg_desc_len"),
        )
        result.write.mode("overwrite").parquet(f"{out_dir}/fx_lookup_join")
        return result.count()
    finally:
        spark.conf.set("spark.sql.autoBroadcastJoinThreshold", prev_thr)
        spark.conf.set("spark.sql.join.preferSortMergeJoin", prev_smj)
