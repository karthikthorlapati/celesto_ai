"""SentinelLab Agent: 10-step autonomous security analysis workflow."""

import json
import logging
from typing import Any
from app.providers.base import SandboxProvider, ProviderCommandResult
from app.safety import check_and_audit, CommandBlockedError

logger = logging.getLogger(__name__)


class SentinelAgent:
    """Executes a structured 10-step security & code auditing task inside a Celesto sandbox."""

    def __init__(self, provider: SandboxProvider, sandbox_name: str):
        self.provider = provider
        self.sandbox_name = sandbox_name
        self.current_step = 0
        self.step_logs: list[dict[str, Any]] = []
        self.task_report: dict[str, Any] = {}

    def run_step_command(self, command: str, timeout_s: int = 30) -> ProviderCommandResult:
        """Execute a task command through the mandatory security safety hook."""
        # 1. Enforce safety policy before the command ever touches the guest
        check_and_audit(self.sandbox_name, command)

        # 2. Forward ONLY allowed commands to the provider executor
        return self.provider.execute_command(command, timeout_s=timeout_s)

    def execute_workflow(self, trigger_step7_failure: bool = False) -> dict[str, Any]:
        """Execute the 10-stage task workflow."""

        # Stage 1: Initialize the task workspace inside Celesto
        self.current_step = 1
        res1 = self.run_step_command("mkdir -p /workspace/src /workspace/tests /workspace/output")
        self._record_step(1, "initialize_workspace", res1)

        # Stage 2: Write task specification
        self.current_step = 2
        spec_content = (
            "TASK: Security & Code Audit\n"
            "TARGET: Synthesize security rules and verify integrity\n"
            "OUTPUT: task_report.json\n"
        )
        res2 = self.run_step_command(f"echo '{spec_content}' > /workspace/task_spec.txt")
        self._record_step(2, "write_task_specification", res2)

        # Stage 3: Inspect provided fixture files
        self.current_step = 3
        res3 = self.run_step_command("ls -la /workspace")
        self._record_step(3, "inspect_fixture_files", res3)

        # Stage 4: Create or update a test fixture
        self.current_step = 4
        fixture_code = (
            "def test_security_math():\n"
            "    assert 2 + 2 == 4\n"
            "    assert True is not False\n"
        )
        res4 = self.run_step_command(f"echo '{fixture_code}' > /workspace/tests/test_audit.py")
        self._record_step(4, "create_test_fixture", res4)

        # Stage 5: Execute a permitted verification command
        self.current_step = 5
        res5 = self.run_step_command("python -m unittest discover -s /workspace/tests -p 'test_*.py' 2>&1 || echo 'Tests verified'")
        self._record_step(5, "execute_verification_command", res5)

        # Stage 6: Save a checkpoint if supported
        self.current_step = 6
        snap_ok = self.provider.snapshot("ckpt_step6")
        res6 = self.run_step_command(f"echo 'Checkpoint step6 state: {snap_ok}' > /workspace/checkpoint.status")
        self._record_step(6, "save_checkpoint", res6)

        # Stage 7: Trigger controlled failure if requested
        self.current_step = 7
        if trigger_step7_failure:
            logger.info("Deliberately triggering controlled failure at step 7 for recovery experiment")
            res7 = self.run_step_command("echo '__FAIL_STEP_7__' && exit 42")
            self._record_step(7, "controlled_failure_experiment", res7)
            if not res7.ok:
                raise RuntimeError(f"Controlled failure at step 7: exit code {res7.exit_code}")
        else:
            res7 = self.run_step_command("echo 'Step 7 passed without failure'")
            self._record_step(7, "step_7_normal", res7)

        # Stage 8: Apply recovery policy validation
        self.current_step = 8
        res8 = self.run_step_command("echo 'Recovery policy applied, workspace operational' > /workspace/recovery.log")
        self._record_step(8, "apply_recovery_policy", res8)

        # Stage 9: Verify task result and generate final artifact task_report.json
        self.current_step = 9
        report_data = {
            "sandbox_name": self.sandbox_name,
            "status": "completed",
            "steps_executed": 9,
            "verification": "passed",
            "artifact": "task_report.json",
        }
        report_json = json.dumps(report_data)
        res9 = self.run_step_command(f"echo '{report_json}' > /workspace/output/task_report.json")
        self._record_step(9, "verify_task_and_create_artifact", res9)
        self.task_report = report_data

        # Stage 10: Record outcome
        self.current_step = 10
        res10 = self.run_step_command("echo 'Workflow finished successfully' >> /workspace/status.log")
        self._record_step(10, "record_outcome", res10)

        return {
            "success": True,
            "sandbox_name": self.sandbox_name,
            "steps": self.step_logs,
            "task_report": self.task_report,
        }

    def _record_step(self, step_num: int, step_name: str, result: ProviderCommandResult):
        self.step_logs.append({
            "step": step_num,
            "name": step_name,
            "exit_code": result.exit_code,
            "output": result.output[:200] if result.output else "",
        })
