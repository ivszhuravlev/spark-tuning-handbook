#!/usr/bin/env python3
"""Read-only snapshot of a Spark application from History Server or live UI REST (/api/v1)."""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

MAX_BYTES = 20 * 1024 * 1024
REDACT = re.compile(r"(secret|password|token|credential|access[._-]?key|private[._-]?key|keytab|cookie)", re.I)


def _ssl(ca_file: str | None) -> ssl.SSLContext:
    return ssl.create_default_context(cafile=ca_file)


class SparkRest:
    def __init__(self, base: str, timeout: float, ca_file: str | None) -> None:
        root = base.rstrip("/")
        self.base = root if root.endswith("/api/v1") else f"{root}/api/v1"
        self.timeout = timeout
        self.ctx = _ssl(ca_file)
        self.headers = {"Accept": "application/json", "User-Agent": "spark-ui-snapshot/1"}
        auth = os.getenv("SPARK_UI_AUTHORIZATION") or os.getenv("SPARK_HISTORY_AUTHORIZATION")
        cookie = os.getenv("SPARK_UI_COOKIE") or os.getenv("SPARK_HISTORY_COOKIE")
        if auth:
            self.headers["Authorization"] = auth
        if cookie:
            self.headers["Cookie"] = cookie
        extra = os.getenv("SPARK_UI_HEADERS_JSON") or os.getenv("SPARK_HISTORY_HEADERS_JSON")
        if extra:
            parsed = json.loads(extra)
            if not isinstance(parsed, dict):
                raise ValueError("header JSON must be an object")
            for k, v in parsed.items():
                if not isinstance(k, str) or not isinstance(v, str):
                    raise ValueError("headers must be strings")
                self.headers[k] = v

    def get(self, path: str, **query: Any) -> Any:
        q = [(k, i) for k, v in query.items() if v is not None for i in (v if isinstance(v, list) else [v])]
        url = f"{self.base}/{path.lstrip('/')}"
        if q:
            url += "?" + urlencode(q)
        req = Request(url, headers=self.headers, method="GET")
        try:
            with urlopen(req, timeout=self.timeout, context=self.ctx) as resp:
                body = resp.read(MAX_BYTES + 1)
        except HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code} for {path}") from exc
        except URLError as exc:
            raise RuntimeError(f"unreachable {path}: {exc.reason}") from exc
        if len(body) > MAX_BYTES:
            raise RuntimeError("response too large")
        return json.loads(body)


def app_join(app_id: str, suffix: str) -> str:
    return f"applications/{quote(app_id, safe='/')}/{suffix.lstrip('/')}"


def redact_env(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"available": False}
    props = []
    for entry in payload.get("sparkProperties") or []:
        if not isinstance(entry, list) or len(entry) < 2:
            continue
        key, val = str(entry[0]), entry[1]
        props.append([key, "<redacted>" if REDACT.search(key) else val])
    return {"runtime": payload.get("runtime"), "sparkProperties": props}


def duration_ms(stage: dict[str, Any]) -> float:
    def parse(v: Any) -> datetime | None:
        if not isinstance(v, str):
            return None
        try:
            return datetime.fromisoformat(v.replace("GMT", "+00:00").replace("Z", "+00:00"))
        except ValueError:
            return None

    start, end = parse(stage.get("submissionTime")), parse(stage.get("completionTime"))
    if start and end:
        return max(0.0, (end - start).total_seconds() * 1000)
    return float(stage.get("executorRunTime") or 0)


def with_tasks(client: SparkRest, app_id: str, stages: list[dict[str, Any]], task_limit: int, failed: bool) -> list[dict[str, Any]]:
    out = []
    for st in stages:
        sid, att = st.get("stageId"), st.get("attemptId", 0)
        if sid is None:
            continue
        root = app_join(app_id, f"stages/{sid}/{att}")
        item: dict[str, Any] = {"stage": st}
        try:
            item["taskSummary"] = client.get(f"{root}/taskSummary", quantiles="0.0,0.5,0.95,0.99,1.0")
            item["tasks"] = client.get(
                f"{root}/taskList",
                offset=0,
                length=task_limit,
                sortBy="-runtime" if not failed else None,
                status="failed" if failed else None,
            )
        except RuntimeError as exc:
            item["error"] = str(exc)
        out.append(item)
    return out


def snapshot(client: SparkRest, app_id: str, stage_limit: int, task_limit: int) -> dict[str, Any]:
    stages = client.get(app_join(app_id, "stages"), withSummaries="true", quantiles="0.0,0.5,0.95,0.99,1.0")
    if not isinstance(stages, list):
        stages = []
    longest = sorted(stages, key=duration_ms, reverse=True)[:stage_limit]
    failed = [s for s in stages if str(s.get("status", "")).lower() == "failed"][:stage_limit]
    return {
        "applicationId": app_id,
        "jobs": client.get(app_join(app_id, "jobs")),
        "longestStages": with_tasks(client, app_id, longest, task_limit, False),
        "failedStages": with_tasks(client, app_id, failed, task_limit, True),
        "executors": client.get(app_join(app_id, "allexecutors")),
        "environment": redact_env(client.get(app_join(app_id, "environment"))),
        "sql": client.get(app_join(app_id, "sql"), details="false", planDescription="false", offset=0, length=100),
    }


def sql_detail(client: SparkRest, app_id: str, execution_id: str, stage_limit: int, task_limit: int) -> dict[str, Any]:
    base = snapshot(client, app_id, stage_limit, task_limit)
    base["sqlExecution"] = client.get(
        app_join(app_id, f"sql/{quote(execution_id, safe='')}"),
        details="true",
        planDescription="true",
    )
    return base


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default=os.getenv("SPARK_UI_URL") or os.getenv("SPARK_HISTORY_URL"))
    p.add_argument("--timeout", type=float, default=20.0)
    p.add_argument("--ca-file")
    p.add_argument("--stage-limit", type=int, default=8)
    p.add_argument("--task-limit", type=int, default=20)
    sub = p.add_subparsers(dest="cmd", required=True)
    apps = sub.add_parser("apps")
    apps.add_argument("--status", choices=["completed", "running"])
    apps.add_argument("--limit", type=int, default=50)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--app-id", required=True)
    sqlp = sub.add_parser("sql")
    sqlp.add_argument("--app-id", required=True)
    sqlp.add_argument("--execution-id", required=True)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not args.base_url:
        raise SystemExit("Set --base-url or SPARK_UI_URL (live UI, e.g. http://localhost:4040) or SPARK_HISTORY_URL")
    if not 1 <= args.stage_limit <= 50 or not 1 <= args.task_limit <= 200:
        raise SystemExit("stage-limit 1-50, task-limit 1-200")
    client = SparkRest(args.base_url, args.timeout, args.ca_file)
    if args.cmd == "apps":
        payload = client.get("applications", status=args.status, limit=args.limit)
    elif args.cmd == "snapshot":
        payload = snapshot(client, args.app_id, args.stage_limit, args.task_limit)
    else:
        payload = sql_detail(client, args.app_id, args.execution_id, args.stage_limit, args.task_limit)
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
