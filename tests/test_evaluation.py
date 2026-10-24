"""Automated tests for evaluation metrics calculation and evaluation runner."""

import pytest
import tempfile
from pathlib import Path
from app.evaluation import calculate_metrics, run_evaluations
from app.providers.test_provider import TestProvider


def test_calculate_metrics_odd_and_even_runs():
    """Verify statistical calculations for both odd and even run counts."""
    # Test odd count (3 runs)
    odd_runs = [
        {"sandbox_name": "sbx-test01a1b2c3", "fresh": True, "success": True, "wall_clock_s": 1.0, "boot_to_ready_s": 0.1, "cost_usd": 0.00001},
        {"sandbox_name": "sbx-test02d4e5f6", "fresh": True, "success": True, "wall_clock_s": 2.0, "boot_to_ready_s": 0.2, "cost_usd": 0.00002},
        {"sandbox_name": "sbx-test03g7h8i9", "fresh": True, "success": False, "wall_clock_s": 3.0, "boot_to_ready_s": 0.3, "cost_usd": 0.00003},
    ]
    res_odd = calculate_metrics(odd_runs)
    assert res_odd["run_count"] == 3
    assert res_odd["success_rate"] == round(2 / 3, 4)
    assert res_odd["median_wall_clock_s"] == 2.0
    assert res_odd["p90_wall_clock_s"] == 3.0
    assert res_odd["median_boot_to_ready_s"] == 0.2
    assert res_odd["total_cost_usd"] == 0.00006

    # Test even count (2 runs)
    even_runs = [
        {"sandbox_name": "sbx-test01a1b2c3", "fresh": True, "success": True, "wall_clock_s": 1.0, "boot_to_ready_s": 0.1, "cost_usd": 0.00001},
        {"sandbox_name": "sbx-test02d4e5f6", "fresh": True, "success": True, "wall_clock_s": 3.0, "boot_to_ready_s": 0.3, "cost_usd": 0.00002},
    ]
    res_even = calculate_metrics(even_runs)
    assert res_even["run_count"] == 2
    assert res_even["median_wall_clock_s"] == 2.0
    assert res_even["median_boot_to_ready_s"] == 0.2


def test_calculate_metrics_empty_raises():
    """Verify calculate_metrics raises ValueError on empty list."""
    with pytest.raises(ValueError, match="empty run list"):
        calculate_metrics([])


def test_run_evaluations_small_batch():
    """Verify run_evaluations executes requested batch and saves output."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        out_path = Path(f.name)

    provider = TestProvider()
    metrics = run_evaluations(count=2, provider=provider, output_path=out_path)

    assert metrics["run_count"] == 2
    assert out_path.exists()

    if out_path.exists():
        out_path.unlink()
