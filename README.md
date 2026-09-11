# Spark Deep Dive

A hands-on course on Apache Spark internals - from cluster architecture to performance tuning.
Each topic is explored with real data in Jupyter notebooks connected to a local Standalone cluster.

---

## Datasets

Experiments use these sources:

Transaction Categorization (Hugging Face, **gated** — accept terms and `hf auth login`)
https://huggingface.co/datasets/mitulshah/transaction-categorization

NYC Yellow Taxi Trip Records (2024, public TLC files)
https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page

FreshRetailNet-50K (Hugging Face, optional; notebooks 01-05 do not read it)
https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K

Notebooks 01-02 read the transaction parquet. Notebooks 03-05 read taxi parquet. Schema-compatible samples from `scripts/prepare_local_data.py` are enough to finish the course.

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

## Spark skills (portable)

Two `SKILL.md` files for Spark performance tuning and debugging (any Spark UI). Not a map of the notebooks. Markdown only.

- `skills/spark-performance-tuning/SKILL.md`
- `skills/spark-debugging/SKILL.md`

See `skills/README.md`. `skill-tests/` is a separate eval: same jobs with vs without those packages.

## Environment

- Local Spark Standalone cluster — 2 workers, 2 cores each, 2 GB each
- Jupyter driver connected to `spark://spark-master:7077` inside Compose (`localhost:7077` from the host)
- Spark **4.0.2** for the Mac/Linux Docker path (image `apache/spark:4.0.2-python3`)
- Public datasets from Hugging Face / NYC TLC
- Supported: Windows (native Spark), Mac/Linux (Docker Desktop)

---

## Mac / Linux: Docker

Runs a full Standalone cluster (master + 2 workers + JupyterLab) in Docker. No local Java or Spark install on the Mac. The `apache/spark:4.0.2-python3` image publishes `linux/arm64`, so Apple Silicon runs natively. Give Docker Desktop **at least 8 GB RAM**.

JupyterLab has **no token** (`ServerApp.token` is empty). Use it only on localhost.

Do **not** attach a Mac-native PySpark driver to the Docker master. Executors run in worker containers and must open RPC back to the driver; that only works when the driver is the Jupyter container (`spark.driver.host=spark-jupyter`). Run notebooks and jobs from JupyterLab or `docker compose exec jupyter ...`.

### Prerequisites

- Docker Desktop (Compose v2)

### Start

```bash
docker compose up --build -d
```

pandas, PyArrow, and JupyterLab are baked into `docker/jupyter/Dockerfile`. Rebuild after changing that file: `docker compose build jupyter`.

Wait until workers register (Spark Master UI should show 2 workers):

```bash
docker compose ps
```

- JupyterLab: http://localhost:8888 (no token or password)
- Spark Master UI: http://localhost:8080
- Spark App UI: http://localhost:4040 (after the first notebook or job)

### Sample data (enough for every notebook)

From the Jupyter container (uses the image Python, no host packages):

```bash
docker compose exec jupyter python /scripts/prepare_local_data.py
```

This writes schema-compatible `data/transaction_cat.parquet` and `data/taxi/*.parquet` on the bind mount. Saved notebook outputs were captured on larger files, so row counts and timings will differ.

### Stop

```bash
docker compose down
```

### Other commands

```bash
docker compose logs -f           # tail all container logs
docker compose exec jupyter bash # shell inside Jupyter container
docker compose ps                # show running containers
docker compose exec jupyter python /skill-tests/launch.py
```

### Datasets

Place files in `data/` (bind-mounted into every Spark container at `/data`).

`mitulshah/transaction-categorization` is **gated** on Hugging Face: `hf download` returns 401 until you run `hf auth login` and accept the dataset terms on the Hub page. NYC taxi files are public.

Expected layout:

```
data/
├── transaction_cat.parquet     # HuggingFace: mitulshah/transaction-categorization
├── retail_net.parquet          # optional; notebooks 01-05 do not read it
└── taxi/
    ├── yellow_tripdata_sample_01.parquet   # from prepare_local_data.py
    └── yellow_tripdata_2024-01.parquet     # optional real TLC files
```

Download Hugging Face datasets with `hf` (`python -m pip install huggingface_hub`, then `hf auth login`, and accept gated-dataset terms):

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

Real TLC files (optional; notebook 03 skips download when `data/taxi` already has parquet):

```bash
mkdir -p data/taxi
for m in $(seq -w 1 12); do
  curl -L --output "data/taxi/yellow_tripdata_2024-${m}.parquet" \
    "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-${m}.parquet"
done
```

### Skill-test jobs

Eval harness (same assignment with vs without `skills/`). Prompt: `skill-tests/TASK.md`. Run from the Jupyter container so the driver stays on the Compose network.

### Troubleshooting (Mac)

- Master UI shows 0 workers: wait ~20s for the healthcheck, then `docker compose logs spark-worker-1`.
- Notebook actions hang on "connecting to driver": confirm you are running inside Jupyter/the `jupyter` container, not a Mac-native `pyspark`.
- Apple Silicon uses the native `linux/arm64` Spark image; first pull can still take a few minutes.
- `docker compose` cannot bind 8888/8080/4040: stop other stacks or change ports in `.env`.

---

## Windows (Company Laptop): Local Spark Standalone + JupyterLab

A minimal, command-only guide to download Spark (Hadoop 3 build), start a local Standalone master + two workers, and launch PySpark in JupyterLab. Details: https://spark.apache.org/docs/latest/spark-standalone.html

Prefer **Spark 4.0.2** so this matches the Mac/Linux Docker course. 4.1.1 also runs; a few UI labels and static-config names can differ.

### Prerequisites

- Java (JDK) 17+
- Python 3.10+
- JupyterLab and pandas:
  ```powershell
  python -m pip install jupyterlab pandas pyarrow numpy
  ```

### Download Spark

Download and extract:

- **Spark release:** 4.0.2 (or 4.1.1)
- **Pre-built package:** Pre-built for Apache Hadoop 3 -> `spark-4.0.2-bin-hadoop3`

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

pyspark --master spark://localhost:7077 `
  --conf spark.sql.catalogImplementation=hive `
  --conf spark.sql.adaptive.enabled=false `
  --conf spark.sql.shuffle.partitions=8 `
  --conf spark.executor.memory=2g
```

Spark UI (after PySpark starts): [http://localhost:4040](http://localhost:4040)

### Quick Reference

| Command | Purpose |
|---------|---------|
| `$env:SPARK_HOME = "C:\path\to\spark-4.0.2-bin-hadoop3"` | Point to extracted Spark folder |
| `$env:PATH = "$env:SPARK_HOME\bin;$env:PATH"` | Make Spark scripts available in current PowerShell |
| `spark-class.cmd org.apache.spark.deploy.master.Master --host localhost --port 7077 --webui-port 8080` | Start Standalone Master |
| `spark-class.cmd org.apache.spark.deploy.worker.Worker spark://localhost:7077 ...` | Start a Standalone Worker (run twice, in two terminals) |
| `cd C:\path\to\your\project` | Run PySpark from the repo folder |
| `$env:PYSPARK_DRIVER_PYTHON = "jupyter"` | Launch PySpark driver as JupyterLab |
| `pyspark --master spark://localhost:7077` | Start PySpark connected to Standalone cluster |
| [http://localhost:4040](http://localhost:4040) | Open Spark application UI |
