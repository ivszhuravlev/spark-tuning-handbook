# Spark performance tuning and debugging

Two `SKILL.md` packages. Attach them to any agent that can read Spark UI (or a query profile). Markdown only — no scripts, no host-specific URLs.

| Skill | When to attach |
| --- | --- |
| [spark-performance-tuning](spark-performance-tuning/SKILL.md) | Too slow or too expensive: shuffle, join strategy, grain, partitioning, UDFs. |
| [spark-debugging](spark-debugging/SKILL.md) | Failed or pathological: first error, OOM vs spill, driver vs executor, task exceptions. |

`skill-tests/` in this repo is a separate with-vs-without eval. It is not part of these packages.
