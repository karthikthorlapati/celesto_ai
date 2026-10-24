#!/usr/bin/env python3
"""CLI script to run automated evaluations and generate reliability reports."""

import os
import sys
import argparse
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.evaluation import run_evaluations
from app.providers.celesto_provider import CelestoProvider
from app.providers.test_provider import TestProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("eval_runner")


def main():
    parser = argparse.ArgumentParser(description="SentinelLab Celesto Evaluation Runner")
    parser.add_argument("--count", type=int, default=20, help="Number of fresh evaluation runs (default: 20)")
    parser.add_argument(
        "--provider",
        choices=["celesto", "test"],
        default="test" if not os.getenv("CELESTO_API_KEY") else "celesto",
        help="Sandbox provider to use (default: celesto if CELESTO_API_KEY else test)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(Path("reports/reliability.json").resolve()),
        help="Path to save reliability.json",
    )
    args = parser.parse_args()

    logger.info(f"Using provider: {args.provider}")
    if args.provider == "celesto":
        provider = CelestoProvider()
    else:
        provider = TestProvider()

    metrics = run_evaluations(
        count=args.count,
        provider=provider,
        output_path=Path(args.output),
    )

    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total Runs:           {metrics['run_count']}")
    print(f"Success Rate:         {metrics['success_rate'] * 100:.1f}%")
    print(f"Median Wall Clock:    {metrics['median_wall_clock_s']:.4f}s")
    print(f"P90 Wall Clock:       {metrics['p90_wall_clock_s']:.4f}s")
    print(f"Median Boot-to-Ready: {metrics['median_boot_to_ready_s']:.4f}s")
    print(f"Total Cost (USD):     ${metrics['total_cost_usd']:.6f}")
    print(f"Report Output:        {args.output}")
    print("=" * 60)


if __name__ == "__main__":
    main()
