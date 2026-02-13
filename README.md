# Spark Deep Dive

A hands-on course on Apache Spark internals - from cluster architecture to performance tuning.
Each topic is explored with real data in Jupyter notebooks connected to a local Standalone cluster.

---

## Datasets

All experiments are built on two public datasets from Hugging Face:

Transaction Categorization
https://huggingface.co/datasets/mitulshah/transaction-categorization

FreshRetailNet-50K (Retail Sales)
https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K

---

## Topics

### 01 - Spark Architecture & Execution Model
- End-to-end query execution (Job -> Stage -> Task breakdown)
- Narrow vs. wide transformations and why the distinction matters
- Lazy evaluation and what it enables
- Client mode vs. Cluster mode

### 02 - Catalyst Optimizer & Query Planning
- Catalyst optimizer phases (parsing -> analysis -> logical optimization -> physical planning)
- Predicate pushdown
- Reading and interpreting execution plans (`.explain()`)
- Cost-Based Optimization (CBO) vs. rule-based

### 03 - Shuffle
- What is a shuffle, when does it happen, and why is it expensive
- Minimizing and optimizing shuffle

### 04 - Joins
- Join strategies: Broadcast Hash, Sort-Merge, Shuffle Hash
- Broadcast joins in depth
- Handling data skew in joins

### 05 - Partitioning & Data Organization
- `repartition()` vs. `coalesce()`
- Partitioning vs. bucketing

### 06 - Memory Management & Troubleshooting
- Spark's memory model (execution vs. storage memory)
- Diagnosing and fixing OOM errors
- Tungsten execution engine & UDF performance

### 07 - Performance Tuning & Operations
- Adaptive Query Execution (AQE)
- Broadcast variables and accumulators
- Dynamic resource allocation
- Speculative execution
- Fault tolerance and task/stage failures

---

## Environment

- Local Spark Standalone cluster (Windows)
- 2 Workers
- Jupyter Driver connected to `spark://localhost:7077`
- Public datasets from Hugging Face

---

## Windows (Company Laptop): Local Spark Standalone + JupyterLab

A minimal, command-only guide to download Spark 4.1.1 (Hadoop 3 build), start a local Standalone master + two workers, and launch PySpark in JupyterLab.

### Prerequisites

- Java (JDK) 17+
- Python 3.10+
- JupyterLab:
  ```powershell
  python -m pip install jupyterlab
  ```

### Download Spark

Download and extract:

- **Spark release:** 4.1.1
- **Pre-built package:** Pre-built for Apache Hadoop 3 -> `spark-4.1.1-bin-hadoop3`

### PowerShell - environment setup

> Replace the placeholder paths with your own.

```powershell
# Example placeholder path (replace)
$env:SPARK_HOME = "C:\path\to\spark-4.1.1-bin-hadoop3"

# Add Spark to PATH for this PowerShell session
$env:PATH = "$env:SPARK_HOME\bin;$env:PATH"
```

### Start Standalone Master and two Workers

Open three PowerShell windows (Master + Worker 1 + Worker 2).

> Spark's `sbin/*` launch scripts do not support Windows - start master/workers directly.

**PowerShell window 1 - Master:**

```powershell
spark-class.cmd org.apache.spark.deploy.master.Master --host localhost --port 7077 --webui-port 8080
```

**PowerShell window 2 - Worker 1:**

```powershell
spark-class.cmd org.apache.spark.deploy.worker.Worker spark://localhost:7077 --cores 2 --memory 2g --webui-port 8081
```

**PowerShell window 3 - Worker 2:**

```powershell
spark-class.cmd org.apache.spark.deploy.worker.Worker spark://localhost:7077 --cores 2 --memory 2g --webui-port 8082
```

### Start PySpark with JupyterLab

New PowerShell window:

```powershell
# Example placeholder path (replace with your repo)
cd C:\path\to\your\project

$env:PYSPARK_DRIVER_PYTHON = "jupyter"
$env:PYSPARK_DRIVER_PYTHON_OPTS = "lab"

pyspark --master spark://localhost:7077
```

Spark UI (after PySpark starts): [http://localhost:4040](http://localhost:4040)

### Quick Reference

| Command | Purpose |
|---------|---------|
| `$env:SPARK_HOME = "C:\path\to\spark-4.1.1-bin-hadoop3"` | Point to extracted Spark folder |
| `$env:PATH = "$env:SPARK_HOME\bin;$env:PATH"` | Make Spark scripts available in current PowerShell |
| `spark-class.cmd org.apache.spark.deploy.master.Master --host localhost --port 7077 --webui-port 8080` | Start Standalone Master |
| `spark-class.cmd org.apache.spark.deploy.worker.Worker spark://localhost:7077 ...` | Start a Standalone Worker (run twice, in two terminals) |
| `cd C:\path\to\your\project` | Run PySpark from the repo folder |
| `$env:PYSPARK_DRIVER_PYTHON = "jupyter"` | Launch PySpark driver as JupyterLab |
| `pyspark --master spark://localhost:7077` | Start PySpark connected to Standalone cluster |
| [http://localhost:4040](http://localhost:4040) | Open Spark application UI |