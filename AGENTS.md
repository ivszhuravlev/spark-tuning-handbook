# Agent notes

This repo is a Spark 4.0.2 internals handbook on a local Standalone cluster.

1. Load project skills under `.cursor/skills/` (start with `spark-tuning-handbook`).
2. Prefer Spark UI and physical plans over guessing configs. AQE stays off unless the task is AQE.
3. Mac/Linux Docker: run Spark from the Jupyter container, not a host `pyspark`.
4. `skill-tests/TASK.md` is an eval of those skills. Do not expect an answer key in git.
