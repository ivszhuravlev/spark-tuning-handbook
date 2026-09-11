# Assignment

The jobs in `skill-tests/workloads/` are shaped like ordinary batch ETL. On the handbook cluster they take too long, shuffle more than they should, or fail.

Bring the cluster up from the repo README (Mac/Linux: Docker). Put data in `data/` (`scripts/prepare_local_data.py` if you do not have the Hub/TLC files). Then run:

```bash
docker compose exec jupyter python /skill-tests/launch.py
```

Or open `run_skill_tests.ipynb` in JupyterLab. Spark UI: http://localhost:4040 while the session is alive.

Use the Spark UI and the physical plan. Fix the jobs. Re-run until runtimes are reasonable, stage/task shape looks healthy, and nothing fails unexpectedly.

Do not expect a solution write-up in this repository. Diagnose from the job code, the physical plan, and the Spark UI.
