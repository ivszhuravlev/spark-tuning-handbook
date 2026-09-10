"""QC gate using Spark native error signalling."""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, expr


def run(spark: SparkSession, txn_path: str, out_dir: str) -> int:
    spark.sparkContext.setJobGroup("qc_reject", "qc_reject")
    df = spark.read.parquet(txn_path)
    flagged = df.withColumn(
        "policy_country",
        when(col("country") == "USA", expr("raise_error('policy backend timeout')")).otherwise(col("country")),
    )
    flagged.write.mode("overwrite").parquet(f"{out_dir}/qc_reject")
    return flagged.count()
