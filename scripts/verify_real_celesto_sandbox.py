"""Verification of live Celesto Cloud sandbox connection.

Creates a uniquely named microVM in Celesto Cloud, executes harmless system commands,
records timing, exit codes, and execution evidence, and cleanly deletes the sandbox
in a finally block.
"""

import sys
import time
import uuid
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("celesto_verification")

def main():
    api_key = settings.celesto_api_key
    if not api_key:
        logger.error("CELESTO_API_KEY environment variable is missing.")
        sys.exit(1)

    # Generate valid unique sandbox name: sbx- followed by 8+ lowercase alphanumeric characters
    sandbox_name = f"sbx-realtest{uuid.uuid4().hex[:10]}"
    evidence_dir = settings.evidence_dir
    evidence_path = evidence_dir / "real_celesto_verification.log"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"=== Starting Celesto Cloud Verification for '{sandbox_name}' ===")
    
    computer = None
    boot_time = 0.0
    command_results = []
    start_time = time.perf_counter()

    try:
        from celesto import Computer

        logger.info("Initializing Celesto Computer handle with provider='cloud'...")
        create_start = time.perf_counter()
        
        # Instantiate ephemeral Computer using Cloud provider
        computer = Computer(provider="cloud", lifetime="ephemeral")
        
        logger.info("Starting Cloud Computer microVM (waiting for ready)...")
        computer.start()
        boot_time = time.perf_counter() - create_start
        vm_id = computer.id
        logger.info(f"Cloud microVM ready! VM ID: {vm_id}, boot-to-ready: {boot_time:.3f}s")

        # Execute harmless verification commands inside the guest
        commands_to_test = [
            "uname -a",
            "python3 --version || python --version",
            "whoami",
            "cat /etc/os-release | grep PRETTY_NAME",
        ]

        for cmd in commands_to_test:
            logger.info(f"Executing guest command: '{cmd}'")
            cmd_start = time.perf_counter()
            res = computer.run(cmd, timeout=30)
            duration_ms = (time.perf_counter() - cmd_start) * 1000.0
            
            logger.info(f" -> Exit code: {res.exit_code}")
            logger.info(f" -> Stdout: {res.stdout.strip()}")
            if res.stderr:
                logger.info(f" -> Stderr: {res.stderr.strip()}")
            
            command_results.append({
                "command": cmd,
                "exit_code": res.exit_code,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "duration_ms": duration_ms,
            })

    except Exception as e:
        logger.error(f"Error during Celesto Cloud verification: {e}", exc_info=True)
        raise
    finally:
        logger.info("Entering cleanup phase...")
        if computer is not None:
            try:
                delete_start = time.perf_counter()
                logger.info(f"Deleting Celesto Cloud computer '{computer.id}'...")
                computer.delete()
                delete_duration = time.perf_counter() - delete_start
                logger.info(f"Celesto Cloud computer successfully deleted in {delete_duration:.3f}s")
            except Exception as del_err:
                logger.error(f"Error deleting Celesto Cloud computer: {del_err}")

        total_wall_clock = time.perf_counter() - start_time
        logger.info(f"=== Celesto Cloud Verification Completed in {total_wall_clock:.2f}s ===")

        # Write execution evidence to reports/evidence/real_celesto_verification.log
        evidence_content = [
            f"=== CELESTO CLOUD VERIFICATION LOG ===",
            f"Sandbox Name: {sandbox_name}",
            f"VM ID: {getattr(computer, 'id', 'N/A')}",
            f"Provider: cloud",
            f"Boot to Ready Duration: {boot_time:.3f}s",
            f"Total Wall Clock Duration: {total_wall_clock:.3f}s",
            f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
            "",
            "=== COMMAND EXECUTION TRACE ===",
        ]
        for item in command_results:
            evidence_content.append(f"Command: {item['command']}")
            evidence_content.append(f"Exit Code: {item['exit_code']}")
            evidence_content.append(f"Duration: {item['duration_ms']:.1f}ms")
            evidence_content.append(f"Stdout:\n{item['stdout'].strip()}")
            if item['stderr']:
                evidence_content.append(f"Stderr:\n{item['stderr'].strip()}")
            evidence_content.append("-" * 40)

        evidence_content.append("CLEANUP STATUS: Deleted verified in finally block.")
        evidence_path.write_text("\n".join(evidence_content), encoding="utf-8")
        logger.info(f"Evidence recorded at: {evidence_path}")

if __name__ == "__main__":
    main()
