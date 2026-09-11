# Spark performance tuning and debugging

Portable agent skills. Attach them to Genie, Claude, Codex, or any harness that loads a `SKILL.md` directory. They are **not** a walkthrough of this repo’s notebooks and they do not mention the eval jobs.

Each skill is self-contained (symlink one folder into `~/.claude/skills`, `~/.codex/skills`, `.cursor/skills`, …).

| Skill | When to attach |
| --- | --- |
| [spark-performance-tuning](spark-performance-tuning/SKILL.md) | Job is too slow or too expensive. Cut shuffle, fix join strategy, partitioning, fan-out, UDFs. |
| [spark-debugging](spark-debugging/SKILL.md) | Job failed or is pathological. Find the first error: OOM vs spill, task exceptions, driver vs executor, fetch-fail fallout. |

Both skills pull a read-only snapshot from the **live Spark UI** (`:4040`) or **History Server** (`:18080`) via `/api/v1` (`scripts/spark_ui_snapshot.py`). Databricks job Spark UI speaks the same API.

```bash
export SPARK_UI_URL="http://localhost:4040"
python3 skills/spark-performance-tuning/scripts/spark_ui_snapshot.py snapshot --app-id <id>
```

Auth: `SPARK_UI_AUTHORIZATION` or `SPARK_HISTORY_AUTHORIZATION`. TLS stays verified.

`skill-tests/` in this repository is a separate eval (same jobs with vs without these skills). It is not part of the skill packages.
