from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# Permit direct execution with `python3 scripts/...` without requiring an editable install.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.data.quality import align_nav_panel
from backend.app.domain.schemas import BacktestRequest
from backend.app.engine.backtest import run_backtest
from backend.app.sec.cache import load_nav_panel

SUMMARY_KEYS = [
    "ending_value",
    "twrr",
    "twrr_cagr",
    "volatility",
    "sharpe",
    "max_drawdown",
    "benchmark_excess_return",
    "cashflow_count",
    "rebalance_count",
    "total_contributed",
    "total_withdrawn",
    "total_costs",
]
TOLERANCE = 1e-8
RUNS_DIR = PROJECT_ROOT / "data/runs"
MISSING = object()


@contextmanager
def project_root_working_directory():
    """Use the cache module's project-relative paths without changing the caller's cwd."""
    original_directory = Path.cwd()
    os.chdir(PROJECT_ROOT)
    try:
        yield
    finally:
        os.chdir(original_directory)


def verify_run_reproducibility(run_id: str) -> dict[str, Any]:
    run_dir = RUNS_DIR / run_id
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Saved run directory not found: {run_dir}")
    for artifact_name in ("request.json", "result.json"):
        if not (run_dir / artifact_name).is_file():
            raise FileNotFoundError(f"Saved run is missing required artifact: {run_dir / artifact_name}")
    request_payload = json.loads((run_dir / "request.json").read_text(encoding="utf-8"))
    stored_result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    request = BacktestRequest(**request_payload)
    proj_ids = sorted({asset.proj_id for asset in request.assets} | {request.benchmark_proj_id})
    with project_root_working_directory():
        nav = align_nav_panel(load_nav_panel(proj_ids))
    recomputed = run_backtest(request, nav)
    stored_summary_value = stored_result.get("summary")
    recomputed_summary_value = recomputed.get("summary")
    stored_summary = stored_summary_value if isinstance(stored_summary_value, dict) else {}
    recomputed_summary = recomputed_summary_value if isinstance(recomputed_summary_value, dict) else {}
    diffs = {
        key: diff_value(stored_summary.get(key, MISSING), recomputed_summary.get(key, MISSING)) for key in SUMMARY_KEYS
    }
    ok = all(item["match"] for item in diffs.values())
    return {"run_id": run_id, "ok": ok, "tolerance": TOLERANCE, "diffs": diffs}


def diff_value(stored: Any, recomputed: Any) -> dict[str, Any]:
    if stored is MISSING or recomputed is MISSING:
        return {
            "stored": None if stored is MISSING else stored,
            "recomputed": None if recomputed is MISSING else recomputed,
            "abs_diff": None,
            "match": False,
            "missing": {"stored": stored is MISSING, "recomputed": recomputed is MISSING},
        }
    if stored is None or recomputed is None:
        return {"stored": stored, "recomputed": recomputed, "abs_diff": None, "match": stored == recomputed}
    if isinstance(stored, int) and isinstance(recomputed, int):
        return {"stored": stored, "recomputed": recomputed, "abs_diff": abs(stored - recomputed), "match": stored == recomputed}
    abs_diff = abs(float(stored) - float(recomputed))
    return {"stored": stored, "recomputed": recomputed, "abs_diff": abs_diff, "match": abs_diff <= TOLERANCE}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 scripts/sec_verify_run_reproducibility.py <run_id>")
    result = verify_run_reproducibility(sys.argv[1])
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result["ok"]:
        raise SystemExit(1)
