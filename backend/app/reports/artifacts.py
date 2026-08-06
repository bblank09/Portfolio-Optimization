from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.reports.markdown import render_research_report

RUNS_DIR = Path("data/runs")
SEC_MANIFEST_PATH = Path("data/sec/normalized/sec_data_manifest.json")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_sec_manifest(path: Path = SEC_MANIFEST_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"source": "SEC Open Data", "manifest_status": "missing", "path": str(path)}
    manifest = load_json(path)
    manifest.setdefault("source", "SEC Open Data")
    return manifest


def load_run_artifacts(run_id: str, runs_dir: Path = RUNS_DIR) -> dict[str, Any]:
    run_dir = runs_dir / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")
    return {
        "run_dir": run_dir,
        "request": load_json(run_dir / "request.json"),
        "result": load_json(run_dir / "result.json"),
        "manifest": load_sec_manifest(),
    }


def write_research_report(run_id: str, runs_dir: Path = RUNS_DIR) -> Path:
    artifacts = load_run_artifacts(run_id, runs_dir)
    report = render_research_report(
        request=artifacts["request"],
        result=artifacts["result"],
        manifest=artifacts["manifest"],
        quality_issues=artifacts["result"].get("quality_issues", []),
    )
    output = artifacts["run_dir"] / "research_report.md"
    output.write_text(report, encoding="utf-8")
    return output
