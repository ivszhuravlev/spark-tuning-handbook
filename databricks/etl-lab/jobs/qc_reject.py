"""QC gate using Spark native error signalling."""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, expr


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
    spark.sparkContext.setJobGroup("qc_reject", "qc_reject")
    df = _read_txn(spark, txn_path)
    flagged = df.withColumn(
        "policy_country",
        when(col("country") == "USA", expr("raise_error('policy backend timeout')")).otherwise(col("country")),
    )
    _write_out(flagged, out_dir, "qc_reject")
    return flagged.count()
