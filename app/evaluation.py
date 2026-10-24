"""Evaluation runner and numerical metrics calculator for SentinelLab."""

import math
import json
import logging
from pathlib import Path
from typing import Any
from app.config import settings
from app.orchestrator import RunOrchestrator, generate_sandbox_name
from app.providers.base import SandboxProvider

logger = logging.getLogger(__name__)


def calculate_metrics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate exact numerical metrics from run records according to specification.

    - Runs sorted by ascending wall_clock_s
    - Success rate = successful runs / total runs
    - Median = middle value or average of two middle values
    - P90 = value at one-based rank ceil(0.90 * n)
    - Total cost = sum of costs
    """
    if not runs:
        raise ValueError("Cannot calculate metrics for empty run list")

    n = len(runs)
    # Sort runs by ascending wall_clock_s
    sorted_by_wall = sorted(runs, key=lambda r: r["wall_clock_s"])

    # Success rate
    success_count = sum(1 for r in sorted_by_wall if r.get("success", False))
    success_rate = round(success_count / n, 4)

    # Median wall_clock_s
    wall_clocks = [r["wall_clock_s"] for r in sorted_by_wall]
    if n % 2 == 1:
        median_wall_clock_s = wall_clocks[n // 2]
    else:
        median_wall_clock_s = round((wall_clocks[n // 2 - 1] + wall_clocks[n // 2]) / 2.0, 4)

    # P90 wall_clock_s: ceil(0.90 * n) (1-indexed rank)
    p90_idx = math.ceil(0.90 * n) - 1
    p90_wall_clock_s = wall_clocks[p90_idx]

    # Median boot_to_ready_s
    boot_times = sorted([r["boot_to_ready_s"] for r in sorted_by_wall])
    if n % 2 == 1:
        median_boot_to_ready_s = boot_times[n // 2]
    else:
        median_boot_to_ready_s = round((boot_times[n // 2 - 1] + boot_times[n // 2]) / 2.0, 4)

    # Total cost
    total_cost_usd = round(sum(r.get("cost_usd", 0.0) for r in sorted_by_wall), 6)

    return {
        "run_count": n,
        "runs": sorted_by_wall,
        "success_rate": success_rate,
        "median_wall_clock_s": median_wall_clock_s,
        "p90_wall_clock_s": p90_wall_clock_s,
        "median_boot_to_ready_s": median_boot_to_ready_s,
        "total_cost_usd": total_cost_usd,
        "postmortem_path": "reports/postmortem.md",
    }


def run_evaluations(
    count: int = 20,
    provider: SandboxProvider | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Execute at least 20 end-to-end fresh sandbox runs and generate reliability report."""
    output_file = output_path or (settings.BASE_DIR / "reports" / "reliability.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    orchestrator = RunOrchestrator(provider=provider)
    runs: list[dict[str, Any]] = []

    # Check for existing partial progress
    if output_file.exists():
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
                if isinstance(existing, dict) and "runs" in existing:
                    runs = existing["runs"]
                    logger.info(f"Loaded {len(runs)} existing runs for resumption.")
        except Exception as e:
            logger.warning(f"Could not load previous progress: {e}")

    needed = count - len(runs)
    logger.info(f"Starting evaluation runner: {needed} runs needed out of {count}")

    for i in range(needed):
        run_index = len(runs) + 1
        name = generate_sandbox_name(f"eval{run_index:02d}")
        # One run includes deliberate step 7 failure to test recovery in the eval suite
        trigger_failure = (run_index == 7)

        logger.info(f"Running eval {run_index}/{count} in sandbox {name} (trigger_failure={trigger_failure})...")
        res = orchestrator.run_task(
            run_id=f"eval-run-{run_index:03d}",
            sandbox_name=name,
            problem_id=f"eval-prob-{run_index:03d}",
            trigger_step7_failure=trigger_failure,
            recovery_policy="fresh" if trigger_failure else None,
        )

        record = {
            "sandbox_name": res["sandbox_name"],
            "fresh": True,
            "success": res["success"],
            "wall_clock_s": res["wall_clock_s"],
            "boot_to_ready_s": res["boot_to_ready_s"],
            "cost_usd": res["cost_usd"],
        }
        runs.append(record)

        # Save partial progress atomically
        metrics = calculate_metrics(runs)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

    logger.info(f"Evaluation complete. {len(runs)} runs recorded. Report saved to {output_file}")
    return calculate_metrics(runs)
