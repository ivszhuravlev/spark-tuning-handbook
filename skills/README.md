# Spark performance tuning and debugging

Two `SKILL.md` packages for Databricks Genie (or any agent that can open Spark UI / query profile). Markdown only — no scripts, no local URLs.

| Skill | When to attach |
| --- | --- |
| [spark-performance-tuning](spark-performance-tuning/SKILL.md) | Too slow or too expensive: shuffle, join strategy, grain, partitioning, UDFs. |
| [spark-debugging](spark-debugging/SKILL.md) | Failed or pathological: first error, OOM vs spill, driver vs executor, task exceptions. |

Paste or upload the `SKILL.md` into Genie. The agent should use the **job/cluster Spark UI** (or SQL warehouse query profile) in the workspace.

`skill-tests/` in this repo is a separate with-vs-without eval. It is not part of these packages.
