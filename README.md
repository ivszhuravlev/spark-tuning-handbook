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

NYC Yellow Taxi Trip Records (2024)
https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page

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

### 03 - Shuffle, Joins, Partitioning & Data Organization
- What is a shuffle, when does it happen, and why is it expensive
- Minimizing and optimizing shuffle
- Join strategies: Broadcast Hash, Sort-Merge, Shuffle Hash
- Broadcast joins in depth
- Handling data skew in joins
- `repartition()` vs. `coalesce()`
- Partitioning vs. bucketing

### 04 - Memory Management & Troubleshooting
- Spark's memory model (execution vs. storage memory)
- Diagnosing and fixing OOM errors
- Tungsten execution engine & UDF performance

### 05 - Performance Tuning & Operations
- Adaptive Query Execution (AQE)
- Broadcast variables and accumulators
- Dynamic resource allocation
- Speculative execution
- Fault tolerance and task/stage failures

---

**Note**: Adaptive Query Execution (AQE) is a runtime optimization layer on top of Spark’s core physical execution model. We deliberately study Spark with AQE disabled initially to build a deterministic understanding of how plans are generated and executed. AQE can improve performance in many cases, but it does not replace the need to understand fundamental execution mechanisms such as shuffle, partitioning, join strategies, and resource behavior.

## Environment

- Local Spark Standalone cluster — 2 workers, 2 cores each, 2 GB each
- Jupyter Driver connected to `spark://localhost:7077`
- Public datasets from Hugging Face
- Supported: Windows (native), Mac/Linux (Docker)

---

## Mac / Linux: Docker

Runs a full Standalone cluster (master + 2 workers + JupyterLab) in Docker. No local Java or Spark installation required. Apple Silicon (M1/M2/M3) is supported.

### Prerequisites

- Docker Desktop

### Python dependencies

Install pandas and PyArrow inside the Jupyter container (required for Pandas UDF demos in notebook 04):

```bash
docker compose exec jupyter pip install pandas pyarrow
```

Run this once after `docker compose up -d`. No restart needed.

### Start

```bash
docker compose up -d
```

- JupyterLab: http://localhost:8888 (no token or password)
- Spark Master UI: http://localhost:8080
- Spark App UI: http://localhost:4040 (after first notebook run)

### Stop

```bash
docker compose down
```

### Other commands

```bash
docker compose logs -f          # tail all container logs
docker compose exec jupyter bash # shell inside Jupyter container
docker compose ps               # show running containers
```

### Datasets

Place datasets in the `data/` directory before starting notebooks:

```
data/
├── transaction_cat.parquet     # HuggingFace: mitulshah/transaction-categorization
├── retail_net.parquet          # HuggingFace: Dingdong-Inc/FreshRetailNet-50K
└── taxi/
    ├── yellow_tripdata_2024-01.parquet
    └── ... (through 2024-12)   # https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
```

Download HuggingFace datasets with `huggingface-cli` (run `huggingface-cli login` first if needed):

```bash
hf download \
mitulshah/transaction-categorization \
default/train/0000.parquet \
--repo-type dataset \
--local-dir data

mv data/default/train/0000.parquet data/transaction_cat.parquet
rm -rf data/default

hf download \
Dingdong-Inc/FreshRetailNet-50K \
data/train.parquet \
--repo-type dataset \
--local-dir data

mv data/data/train.parquet data/retail_net.parquet
rm -rf data/data
```

Taxi files can be downloaded directly:

```bash
for m in $(seq -w 1 12); do
  curl -O --output-dir data/taxi \
    "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-${m}.parquet"
done
```

---

## Windows (Company Laptop): Local Spark Standalone + JupyterLab

A minimal, command-only guide to download Spark 4.1.1 (Hadoop 3 build), start a local Standalone master + two workers, and launch PySpark in JupyterLab. Details: https://spark.apache.org/docs/latest/spark-standalone.html

### Prerequisites

- Java (JDK) 17+
- Python 3.10+
- JupyterLab and pandas:
  ```powershell
  python -m pip install jupyterlab pandas pyarrow
  ```

### Download Spark

Download and extract:

- **Spark release:** 4.1.1
- **Pre-built package:** Pre-built for Apache Hadoop 3 -> `spark-4.1.1-bin-hadoop3`

### PowerShell - environment setup

Set User variables once via Windows Environment Variables.

**Create variable**: SPARK_HOME = C:\path\to\spark-x.x.x-bin-hadoop3

**Edit Path variable and add**: %SPARK_HOME%\bin

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

pyspark --master spark://localhost:7077 --conf spark.sql.catalogImplementation=hive
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
