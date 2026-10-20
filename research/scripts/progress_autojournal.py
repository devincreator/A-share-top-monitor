#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Append evidence-only research progress after GitHub Actions completions.

This is an execution journal. A green Actions conclusion NEVER certifies market-data
point-in-time availability, model performance, or the four-task dual-80 target.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path("research/progress")
RUNS = ROOT / "runs"
# Isolated researcher workflows only; avoid production collectors/monitor workflows.
ELIGIBLE_PATH = re.compile(r"^\\.github/workflows/(?:research[-_]|v(?:7[6-9]|[89]\\d|\\d{3,})[-_])", re.IGNORECASE)
SELF_PATH = ".github/workflows/research-progress-autojournal.yml"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def api(endpoint: str, repo: str, token: str) -> Any:
    url = f"https://api.github.com/repos/{repo}/{endpoint.lstrip('/')}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "A-share-research-progress-journal",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=35) as res:
        return json.load(res)


def eligible(run: dict) -> bool:
    path = str(run.get("path") or "")
    return (path != SELF_PATH and bool(ELIGIBLE_PATH.match(path)))


def get_research_run(event: dict, event_kind: str, repo: str, token: str):
    """Retrieve authoritative run metadata rather than trusting a narrative summary."""
    if event_kind == "workflow_run":
        run_id = (event.get("workflow_run") or {}).get("id")
        if not run_id:
            raise RuntimeError("workflow_run event has no run ID")
        run = api(f"actions/runs/{int(run_id)}", repo, token)
    elif event_kind == "workflow_dispatch":
        inputs = event.get("inputs") or {}
        run_id = str(inputs.get("source_run_id") or "").strip()
        if run_id:
            if not run_id.isdecimal():
                raise ValueError("source_run_id must be numeric")
            run = api(f"actions/runs/{int(run_id)}", repo, token)
        else:
            return None  # self-reported non-Actions milestone
    elif event_kind == "push":
        runs = api("actions/runs?per_page=50", repo, token).get("workflow_runs", [])
        run = next(
            (r for r in runs if eligible(r) and r.get("status") == "completed"
             and r.get("conclusion") is not None), None
        )
        if run is None:
            raise RuntimeError("No completed researcher workflow available for bootstrap")
        run = api(f"actions/runs/{int(run['id'])}", repo, token)
    else:
        raise RuntimeError(f"Unexpected trigger: {event_kind}")
    if not eligible(run):
        print(f"SKIP: Not a researcher workflow: {run.get('path')}")
        return False
    if run.get("status") != "completed":
        print(f"SKIP: Run not yet completed: {run.get('id')} status={run.get('status')}")
        return False
    head = run.get("head_repository") or {}
    if head and head.get("full_name") != repo:
        print("SKIP: Workflow originated from another repository")
        return False
    if run.get("head_branch") != os.getenv("DEFAULT_RESEARCH_BRANCH", "main"):
        print("SKIP: Non-default branch run")
        return False
    return run


def load_pages(endpoint: str, list_key: str, repo: str, token: str) -> list:
    out = []
    for page in range(1, 11):  # explicit bounded pagination, up to 1000 entries
        connector = "&" if "?" in endpoint else "?"
        data = api(f"{endpoint}{connector}per_page=100&page={page}", repo, token)
        part = data.get(list_key, [])
        out.extend(part)
        if len(part) < 100:
            break
    return out


def github_run_record(run: dict, repo: str, token: str) -> dict:
    id_ = int(run["id"])
    jobs = load_pages(f"actions/runs/{id_}/jobs", "jobs", repo, token)
    artifacts = load_pages(f"actions/runs/{id_}/artifacts", "artifacts", repo, token)
    return {
        "schema_version": 1,
        "record_type": "github_actions_completion",
        "progress_source": "GITHUB_API_AUTHORITATIVE",
        "recorded_at_utc": utc_now(),
        "run_id": id_,
        "run_attempt": int(run.get("run_attempt") or 1),
        "workflow_name": str(run.get("name") or ""),
        "workflow_path": str(run.get("path") or ""),
        "branch": str(run.get("head_branch") or ""),
        "commit_sha": str(run.get("head_sha") or ""),
        "status": str(run.get("status") or ""),
        "conclusion": str(run.get("conclusion") or ""),
        "event": str(run.get("event") or ""),
        "created_at": run.get("created_at"),
        "run_started_at": run.get("run_started_at"),
        "updated_at": run.get("updated_at"),
        "run_url": str(run.get("html_url") or ""),
        "jobs": [
            {
                "id": j.get("id"),
                "name": j.get("name"),
                "status": j.get("status"),
                "conclusion": j.get("conclusion"),
                "started_at": j.get("started_at"),
                "completed_at": j.get("completed_at"),
                "url": j.get("html_url"),
            }
            for j in jobs
        ],
        "artifacts": [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "size_in_bytes": a.get("size_in_bytes"),
                "expired": a.get("expired"),
                "expires_at": a.get("expires_at"),
                "url": a.get("archive_download_url"),
            }
            for a in artifacts
        ],
        "data_gate": "NOT_ASSESSED_BY_AUTOMATIC_JOURNAL",
        "PIT_certified": None,
        "dual80_achieved": None,
        "warning": "An Actions success only means the process exited successfully. Read raw artifacts and research/status/quality_gates.json before declaring scientific or PIT validation.",
    }


def manual_record(event: dict, repo: str) -> dict:
    inputs = event.get("inputs") or {}
    task = str(inputs.get("task_title") or "").strip()
    note = str(inputs.get("summary") or "").strip()
    evidence = str(inputs.get("evidence_url") or "").strip()
    if not task or not note or not evidence:
        raise ValueError("Manual research milestone requires task_title, summary and evidence_url")
    if len(task) > 150 or len(note) > 1800 or len(evidence) > 800:
        raise ValueError("Manual progress input is too long")
    # Evidence must link to this repository's auditable file, commit, issue or run.
    prefix = f"https://github.com/{repo}/"
    if not evidence.startswith(prefix):
        raise ValueError("evidence_url must be a GitHub URL in this repository")
    action_id = os.environ.get("GITHUB_RUN_ID", "0")
    return {
        "schema_version": 1,
        "record_type": "manually_reported_research_milestone",
        "progress_source": "AI_OR_USER_REPORTED_NOT_INDEPENDENTLY_CERTIFIED",
        "recorded_at_utc": utc_now(),
        "run_id": int(action_id),
        "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
        "workflow_name": task,
        "status": "completed",
        "conclusion": str(inputs.get("result") or "unknown"),
        "run_url": f"https://github.com/{repo}/actions/runs/{action_id}",
        "evidence_url": evidence,
        "summary": note,
        "jobs": [],
        "artifacts": [],
        "data_gate": "MANUAL_EVIDENCE_REQUIRES_SEPARATE_QA",
        "PIT_certified": None,
        "dual80_achieved": None,
        "warning": "Manual milestone narrative does not certify PIT or the double-80 criteria.",
    }


def safe_md(txt) -> str:
    return str(txt or "").replace("|", "&#124;").replace("\n", " ").replace("\r", " ")[:100]


def write_history(record: dict):
    RUNS.mkdir(parents=True, exist_ok=True)
    ident = f"{record['run_id']}-attempt-{record['run_attempt']}"
    output = RUNS / f"{ident}.json"
    # Stable files: rerunning the same source run is idempotent except evidence freshness.
    if output.exists():
        old = json.loads(output.read_text(encoding="utf-8"))
        if old.get("status") == record.get("status") and old.get("conclusion") == record.get("conclusion") and old.get("artifacts") == record.get("artifacts"):
            print(f"SKIP duplicate unchanged source-run {ident}")
            return False
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def render_index():
    RUNS.mkdir(parents=True, exist_ok=True)
    records = []
    for path in RUNS.glob("*.json"):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            if d.get("run_id") and d.get("record_type"):
                records.append(d)
        except (json.JSONDecodeError, OSError):
            raise RuntimeError(f"Corrupted research progress entry: {path}")
    records.sort(key=lambda a: (str(a.get("updated_at") or a.get("recorded_at_utc") or ""), int(a["run_id"])), reverse=True)
    if not records:
        raise RuntimeError("No progress entries after journal")
    latest = records[0]
    (ROOT / "latest.json").write_text(
        json.dumps({"updated_at_utc": utc_now(), "entry_count": len(records), "latest": latest}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# 自动研究进度记录（GitHub Actions）",
        "",
        "> 仅代表 **任务执行状态**，不是市场数据历史可得性(PIT)认证，更不是四任务双80成绩。",
        "> 研究数据门禁的唯一授权状态见 [quality_gates.json](../status/quality_gates.json)。",
        "",
        f"已记录 {len(records)} 条研究任务完成记录。按最近时间显示前30条。新AI必须查阅失败结果及相应原始附件。",
        "",
        "| 完成时间(UTC) | 研究任务 | 运行结论 | 证据 |",
        "|---|---|---|---|",
    ]
    for r in records[:30]:
        end = r.get("updated_at") or r.get("recorded_at_utc")
        run_url = r.get("run_url")
        evidence = f"[GitHub Actions]({run_url})" if run_url else "—"
        lines.append(f"| {safe_md(end)} | {safe_md(r.get('workflow_name'))} | {safe_md(r.get('conclusion'))} | {evidence} |")
    lines.extend([
        "",
        "## 如何接续",
        "",
        "1. 先读根目录 [AI_RESEARCH_HANDOFF.md](../../AI_RESEARCH_HANDOFF.md) 与 [执行手册](../NEXT_AI_RUNBOOK.md)。",
        "2. 从 [latest.json](latest.json) 核对任务结论；逐次记录保存在 [runs/](runs/)，包含Jobs和Artifacts链接。",
        "3. 仓库里用于历史数据质量认证的 `research/status/quality_gates.json` **不会**被本工作流自动改为PASS。",
        "4. AI完成聊天内或本地研究（不是Actions）后，必须主动写入带数据证据的完成记录，或用手动触发本进度工作流的 task_title、summary、evidence_url 参数登记。",
        "",
    ])
    (ROOT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"entries": len(records), "latest_run_id": latest["run_id"], "latest_conclusion": latest.get("conclusion")}, ensure_ascii=False))


def main() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GH_TOKEN"]
    kind = os.environ["GITHUB_EVENT_NAME"]
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    run = get_research_run(event, kind, repo, token)
    if run is False:
        return 0
    record = github_run_record(run, repo, token) if run is not None else manual_record(event, repo)
    if write_history(record):
        render_index()
    else:
        print("No progress changes to commit")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, RuntimeError, urllib.error.HTTPError, urllib.error.URLError) as ex:
        print(f"PROGRESS_JOURNAL_ERROR: {type(ex).__name__}: {ex}", file=sys.stderr)
        sys.exit(1)
