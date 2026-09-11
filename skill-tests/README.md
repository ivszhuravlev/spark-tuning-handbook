# Skill tests

Batch jobs used with the handbook cluster. How to run them, and the assignment prompt, are in `TASK.md`.

```bash
docker compose exec jupyter python /skill-tests/launch.py
```

From a host that already has a Standalone master on port 7077:

```bash
export SPARK_MASTER=spark://localhost:7077
python skill-tests/launch.py
```

Spark UI: http://localhost:4040 (`SKILL_TEST_KEEP_UI=1` keeps the session up).
