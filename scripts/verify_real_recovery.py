"""Verify Step 7 failure and fresh sandbox recovery in Celesto Cloud."""

import sys
import json
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings, EVIDENCE_DIR
from app.database import init_db, SessionLocal
from app.orchestrator import RunOrchestrator, generate_sandbox_name
from app.providers.celesto_provider import CelestoProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("real_recovery")

def main():
    if not settings.celesto_api_key:
        logger.error("CELESTO_API_KEY is not set.")
        sys.exit(1)

    init_db()
    db = SessionLocal()

    sandbox_name = generate_sandbox_name("fail7")
    run_id = f"run-recovery-{sandbox_name[4:]}"
    evidence_path = EVIDENCE_DIR / "real_recovery_celesto.log"

    logger.info(f"=== Starting Real Step 7 Failure & Recovery in Celesto Cloud: {run_id} ===")

    provider = CelestoProvider(provider_mode="cloud", api_key=settings.celesto_api_key)
    orchestrator = RunOrchestrator(provider=provider, db=db, default_policy="fresh")

    try:
        result = orchestrator.run_task(
            run_id=run_id,
            sandbox_name=sandbox_name,
            problem_id="problem-real-recovery",
            trigger_step7_failure=True,
            recovery_policy="fresh",
        )
        logger.info("=== Recovery Task Result ===")
        logger.info(json.dumps(result, indent=2))

        evidence_content = {
            "run_id": run_id,
            "original_sandbox": sandbox_name,
            "recovered_sandbox": result["sandbox_name"],
            "policy": "fresh",
            "failed_step": 7,
            "total_steps": 10,
            "recovered": result["recovered"],
            "success": result["success"],
            "task_report": result["task_report"],
            "cleanup_performed": result["cleanup_performed"],
            "cleanup_success": result["cleanup_success"],
        }
        with open(evidence_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(evidence_content, indent=2))
        
        logger.info(f"Real recovery evidence recorded at: {evidence_path}")

    finally:
        db.close()

if __name__ == "__main__":
    main()
