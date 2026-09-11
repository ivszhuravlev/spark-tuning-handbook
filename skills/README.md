# Agent skills

The packages an agent should load are in **`.cursor/skills/`** (Agent Skills layout: one directory per skill, `SKILL.md` inside).

`skill-tests/` is the **eval**: broken-looking batch jobs plus `TASK.md`. It is not the skill library. An agent that only reads `skill-tests/` and never loads `.cursor/skills/` is taking the test without the course.

| Directory | Skill | Use when |
| --- | --- | --- |
| `.cursor/skills/spark-tuning-handbook/` | router | Spark UI / plans / skill-tests / “which notebook applies” |
| `.cursor/skills/spark-architecture-execution/` | architecture | jobs, stages, tasks, narrow vs wide, too many tasks |
| `.cursor/skills/spark-catalyst-planning/` | Catalyst | `explain()`, pushdown, BHJ vs SMJ in the plan |
| `.cursor/skills/spark-shuffle-joins/` | shuffle & joins | shuffle bytes, skew, join keys, repartition |
| `.cursor/skills/spark-memory-troubleshooting/` | memory | OOM, spill, `raise_error`, Python UDFs |
| `.cursor/skills/spark-aqe-operations/` | AQE & ops | AQE, speculation, lineage, static Spark 4 configs |

Run the eval:

```bash
docker compose exec jupyter python /skill-tests/launch.py
```

There is no solution write-up in git. Diagnose from job code, the physical plan, and Spark UI using the skills.
