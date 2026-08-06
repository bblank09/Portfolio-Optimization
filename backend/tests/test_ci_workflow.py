from pathlib import Path

import yaml

WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"


def _load_workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def test_ci_workflow_exists_and_is_valid_yaml():
    assert WORKFLOW_PATH.is_file()
    workflow = _load_workflow()
    assert workflow["jobs"]


def test_ci_workflow_triggers_on_push_and_pr_to_main():
    workflow = _load_workflow()
    # YAML parses the bare key `on:` as the boolean True, not the string "on".
    triggers = workflow[True]
    assert triggers["push"]["branches"] == ["main"]
    assert triggers["pull_request"]["branches"] == ["main"]


def test_ci_workflow_runs_pytest():
    workflow = _load_workflow()
    all_run_steps = " ".join(
        step["run"]
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if "run" in step
    )
    assert "pytest" in all_run_steps


def test_ci_workflow_runs_frontend_build():
    workflow = _load_workflow()
    all_run_steps = " ".join(
        step["run"]
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if "run" in step
    )
    assert "npm run build" in all_run_steps
