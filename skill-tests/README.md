# Skill tests

Batch jobs used with the handbook cluster. The assignment prompt is `TASK.md`.

From the Jupyter container (this is the Mac/Linux Docker path):

```bash
docker compose exec jupyter python /skill-tests/launch.py
```

Or open `notebooks/run_skill_tests.ipynb` in JupyterLab so the job reuses the live session (port 4040 stays on that app).

A Mac-native `pyspark` driver cannot talk to Compose workers. Only use a host driver if master **and** workers run on the same machine:

```bash
export SPARK_MASTER=spark://127.0.0.1:7077
python skill-tests/launch.py
```

Spark UI: http://localhost:4040 (`SKILL_TEST_KEEP_UI=1` keeps a newly created session up).
