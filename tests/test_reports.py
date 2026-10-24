"""Comprehensive report schema, numerical validation, and consistency tests."""

import re
import json
import math
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"

SANDBOX_NAME_RE = re.compile(r"^sbx-[a-z0-9]{8,}$")
ALLOWED_CAPABILITY_IDS = {
    "persistence",
    "snapshots",
    "celestofs",
    "browser",
    "published_ports",
    "network_policy",
    "safety_hooks",
    "host_mounts",
    "coding_agent_preset",
    "agentor_durable",
}


def test_problem_json_schema():
    path = REPORTS_DIR / "problem.json"
    assert path.exists(), "reports/problem.json must exist"
    data = json.loads(path.read_text(encoding="utf-8"))

    assert "who" in data and len(data["who"]) >= 40
    assert "agent_work" in data and len(data["agent_work"]) >= 40
    assert "proof_output" in data and len(data["proof_output"]) >= 20
    assert data.get("idea_source") in ["idea_bank", "original"]


def test_capabilities_json_schema():
    path = REPORTS_DIR / "capabilities.json"
    assert path.exists(), "reports/capabilities.json must exist"
    data = json.loads(path.read_text(encoding="utf-8"))

    assert isinstance(data, list)
    assert len(data) >= 2

    for cap in data:
        assert "id" in cap and cap["id"] in ALLOWED_CAPABILITY_IDS
        assert "why" in cap and len(cap["why"]) >= 80
        assert "evidence_path" in cap
        evidence_file = BASE_DIR / cap["evidence_path"]
        assert evidence_file.exists(), f"Evidence file {cap['evidence_path']} must exist"
        assert evidence_file.stat().st_size > 0


def test_lifecycle_json_schema():
    path = REPORTS_DIR / "lifecycle.json"
    assert path.exists(), "reports/lifecycle.json must exist"
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data.get("cleanup_on_success") is True
    assert data.get("cleanup_on_failure") is True
    assert data.get("cleanup_on_interrupt") is True

    names = data.get("sandbox_names", [])
    assert isinstance(names, list) and len(names) > 0
    # All sandbox names must be unique and match sbx-[a-z0-9]{8,}
    assert len(names) == len(set(names))
    for name in names:
        assert SANDBOX_NAME_RE.match(name), f"Sandbox name '{name}' does not match required format"


def test_reliability_json_schema_and_numerical_metrics():
    path = REPORTS_DIR / "reliability.json"
    assert path.exists(), "reports/reliability.json must exist"
    data = json.loads(path.read_text(encoding="utf-8"))

    runs = data.get("runs", [])
    n = data.get("run_count", 0)
    assert n >= 20
    assert len(runs) == n

    # Check ascending wall_clock_s sort
    wall_clocks = [r["wall_clock_s"] for r in runs]
    assert wall_clocks == sorted(wall_clocks), "runs must be sorted by ascending wall_clock_s"

    for r in runs:
        assert SANDBOX_NAME_RE.match(r["sandbox_name"])
        assert r.get("fresh") is True
        assert isinstance(r.get("success"), bool)
        assert r["wall_clock_s"] >= 0
        assert r["boot_to_ready_s"] >= 0
        assert r["cost_usd"] >= 0

    # Numerical calculation verifications
    # 1. Success rate
    expected_success_rate = round(sum(1 for r in runs if r["success"]) / n, 4)
    assert abs(data["success_rate"] - expected_success_rate) < 0.001

    # 2. Median wall_clock_s
    if n % 2 == 1:
        expected_median_wall = wall_clocks[n // 2]
    else:
        expected_median_wall = round((wall_clocks[n // 2 - 1] + wall_clocks[n // 2]) / 2.0, 4)
    assert abs(data["median_wall_clock_s"] - expected_median_wall) < 0.001

    # 3. P90 wall_clock_s (1-indexed ceil(0.90 * n))
    p90_idx = math.ceil(0.90 * n) - 1
    expected_p90 = wall_clocks[p90_idx]
    assert abs(data["p90_wall_clock_s"] - expected_p90) < 0.001

    # 4. Total cost
    expected_cost = round(sum(r["cost_usd"] for r in runs), 6)
    assert abs(data["total_cost_usd"] - expected_cost) < 0.0001

    # 5. Postmortem reference
    assert data.get("postmortem_path") == "reports/postmortem.md"
    postmortem_file = BASE_DIR / data["postmortem_path"]
    assert postmortem_file.exists()


def test_postmortem_md_length():
    path = REPORTS_DIR / "postmortem.md"
    assert path.exists(), "reports/postmortem.md must exist"
    content = path.read_text(encoding="utf-8")
    assert len(content) >= 200, "Postmortem must be at least 200 characters"


def test_containment_json_schema():
    path = REPORTS_DIR / "containment.json"
    assert path.exists(), "reports/containment.json must exist"
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data.get("attack") in ["prompt_injection_exfil", "destructive_command", "suspicious_package"]
    assert data.get("blocked") is True
    assert data.get("host_untouched") is True

    evidence_paths = data.get("evidence_paths", [])
    assert isinstance(evidence_paths, list) and len(evidence_paths) >= 1
    for p in evidence_paths:
        f = BASE_DIR / p
        assert f.exists(), f"Evidence path '{p}' must exist"
        assert f.stat().st_size > 0


def test_failure_policy_json_and_trace():
    policy_path = REPORTS_DIR / "failure_policy.json"
    assert policy_path.exists(), "reports/failure_policy.json must exist"
    policy_data = json.loads(policy_path.read_text(encoding="utf-8"))

    assert policy_data.get("failed_step") == 7
    assert policy_data.get("total_steps") == 10
    assert policy_data.get("policy") in ["resume", "rollback", "fresh"]
    assert len(policy_data.get("rationale", "")) >= 200
    assert policy_data.get("trace_path") == "reports/failure_trace.jsonl"

    trace_file = BASE_DIR / policy_data["trace_path"]
    assert trace_file.exists(), "reports/failure_trace.jsonl must exist"

    lines = [json.loads(line) for line in trace_file.read_text(encoding="utf-8").strip().splitlines() if line.strip()]
    policy_events = [e for e in lines if e.get("event") == "policy_applied"]
    assert len(policy_events) >= 1
    assert any(e.get("policy") == policy_data["policy"] for e in policy_events)


def test_concurrency_json_schema():
    path = REPORTS_DIR / "concurrency.json"
    assert path.exists(), "reports/concurrency.json must exist"
    data = json.loads(path.read_text(encoding="utf-8"))

    jobs = data.get("jobs", [])
    assert isinstance(jobs, list) and len(jobs) >= 5
    for job in jobs:
        assert SANDBOX_NAME_RE.match(job["sandbox_name"])
        assert "started_at" in job

    assert len(data.get("breakage_notes", "")) >= 40


def test_command_audit_log_format():
    path = LOGS_DIR / "commands.jsonl"
    assert path.exists(), "logs/commands.jsonl must exist"

    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 10, "Should have audited commands from runs"

    has_allow = False
    has_block = False

    for line in lines:
        entry = json.loads(line)
        assert "ts" in entry
        assert SANDBOX_NAME_RE.match(entry["sandbox_name"])
        assert len(entry["command"]) > 0
        assert entry["decision"] in ["allow", "block"]
        assert entry["execution_target"] == "celesto_sandbox"
        if entry["decision"] == "allow":
            has_allow = True
        if entry["decision"] == "block":
            has_block = True

    assert has_allow, "Audit log must contain allowed commands"
    assert has_block, "Audit log must contain blocked commands"


def test_readme_contains_required_phrases():
    readme_path = BASE_DIR / "README.md"
    assert readme_path.exists(), "README.md must exist"
    content = readme_path.read_text(encoding="utf-8")

    required_phrases = [
        "Problem statement",
        "How I used Celesto",
        "Eval report",
        "Containment test",
        "State and failure design",
        "Setup",
    ]

    for phrase in required_phrases:
        assert phrase in content, f"README.md must contain required phrase: '{phrase}'"
