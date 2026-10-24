"""Run a complete 10-step SentinelLab agent workflow inside a real Celesto Cloud sandbox."""

import sys
import json
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.database import init_db, SessionLocal
from app.orchestrator import RunOrchestrator, generate_sandbox_name
from app.providers.celesto_provider import CelestoProvider
from app.ledger import RunLedger

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("real_task_runner")

def main():
    if not settings.celesto_api_key:
        logger.error("CELESTO_API_KEY is not set.")
        sys.exit(1)

    init_db()
    db = SessionLocal()

    sandbox_name = generate_sandbox_name("real")
    run_id = f"run-real-{sandbox_name[4:]}"
    logger.info(f"=== Starting Real Celesto Cloud Task: {run_id} ({sandbox_name}) ===")

    provider = CelestoProvider(provider_mode="cloud", api_key=settings.celesto_api_key)
    orchestrator = RunOrchestrator(provider=provider, db=db, default_policy="fresh")

    try:
        result = orchestrator.run_task(
            run_id=run_id,
            sandbox_name=sandbox_name,
            problem_id="problem-real-audit",
            trigger_step7_failure=False,
        )
        logger.info(f"=== Task Run Result ===")
        logger.info(json.dumps(result, indent=2))

        # Check ledger record
        run_record = RunLedger.get_run(db, run_id)
        if run_record:
            logger.info(f"Ledger record verified: state={run_record.get('state')}, target={run_record.get('execution_target')}")

    finally:
        db.close()

if __name__ == "__main__":
    main()
