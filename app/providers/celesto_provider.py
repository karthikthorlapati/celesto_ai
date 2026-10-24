"""Real Celesto Cloud / Local provider using the official Celesto SDK."""

import os
import time
import logging
from typing import Any
from app.config import settings
from app.providers.base import SandboxProvider, ProviderCommandResult

logger = logging.getLogger(__name__)


class CelestoProvider(SandboxProvider):
    """Executes commands and manages sandbox lifecycles using the official Celesto SDK."""

    def __init__(self, provider_mode: str | None = None, api_key: str | None = None):
        self.provider_mode = provider_mode or settings.celesto_provider
        self.api_key = api_key or settings.celesto_api_key
        self.sandbox_name: str | None = None
        self.computer: Any = None
        self.boot_to_ready_s: float = 0.0
        self.is_ready: bool = False
        self.is_deleted: bool = False
        self.cleanup_error: str | None = None
        self.snapshots: dict[str, Any] = {}

    def create_sandbox(self, name: str, **kwargs: Any) -> str:
        """Create a uniquely named Celesto sandbox computer."""
        self.sandbox_name = name
        self.is_deleted = False
        self.cleanup_error = None
        start_time = time.perf_counter()

        # Set API key in environment if provided
        if self.api_key:
            os.environ["CELESTO_API_KEY"] = self.api_key

        try:
            from celesto import Computer

            # Instantiate Celesto computer
            # Cloud provider is used on Windows or when explicitly selected
            logger.info(
                f"Initializing Celesto computer '{name}' with provider={self.provider_mode}"
            )
            self.computer = Computer(
                provider=self.provider_mode,
                lifetime="ephemeral",
            )
            # Configure network policy if requested
            if kwargs.get("network_mode") == "off":
                try:
                    from _celesto_cloud_api.models.network_policy import NetworkPolicy
                    from _celesto_cloud_api.models.network_policy_mode import NetworkPolicyMode
                    if hasattr(self.computer._provider, "_body"):
                        self.computer._provider._body.network_policy = NetworkPolicy(mode=NetworkPolicyMode.OFF)
                        logger.info(f"Applied network_policy=OFF to Celesto computer '{name}'")
                except Exception as net_err:
                    logger.warning(f"Could not apply network_policy: {net_err}")

            # Ensure computer starts
            self.computer.start()
            self.boot_to_ready_s = max(0.01, time.perf_counter() - start_time)
            self.is_ready = True
            logger.info(
                f"Celesto computer '{name}' started in {self.boot_to_ready_s:.3f}s (id={getattr(self.computer, 'id', 'N/A')})"
            )
            return name
        except Exception as e:
            self.boot_to_ready_s = time.perf_counter() - start_time
            logger.error(f"Failed to initialize Celesto computer '{name}': {e}")
            raise

    def wait_until_ready(self, timeout_s: float = 30.0) -> float:
        """Wait for computer to be responsive."""
        if not self.computer:
            raise RuntimeError("Sandbox has not been created yet.")
        if self.is_ready:
            return self.boot_to_ready_s

        start_wait = time.perf_counter()
        res = self.execute_command("echo READY", timeout_s=int(timeout_s))
        if res.ok:
            self.is_ready = True
            self.boot_to_ready_s = time.perf_counter() - start_wait
            return self.boot_to_ready_s
        raise TimeoutError(f"Celesto computer failed readiness check: {res.stderr}")

    def execute_command(self, command: str, timeout_s: int = 30) -> ProviderCommandResult:
        """Execute a shell command inside the Celesto computer."""
        if not self.computer:
            raise RuntimeError("Sandbox has not been created yet.")
        if self.is_deleted:
            raise RuntimeError("Sandbox has already been deleted.")

        start_time = time.perf_counter()
        try:
            result = self.computer.run(command, timeout=timeout_s)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ProviderCommandResult(
                exit_code=result.exit_code,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"Command execution error in sandbox '{self.sandbox_name}': {e}")
            return ProviderCommandResult(
                exit_code=1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
            )

    def snapshot(self, snapshot_name: str) -> bool:
        """Checkpoint current sandbox state."""
        try:
            if hasattr(self.computer, "snapshot"):
                self.computer.snapshot(snapshot_name)
            self.snapshots[snapshot_name] = True
            return True
        except Exception as e:
            logger.warning(f"Snapshot '{snapshot_name}' not supported by current provider backend: {e}")
            return False

    def restore(self, snapshot_name: str) -> bool:
        """Restore sandbox state from checkpoint."""
        try:
            if hasattr(self.computer, "restore"):
                self.computer.restore(snapshot_name)
                return True
            return snapshot_name in self.snapshots
        except Exception as e:
            logger.warning(f"Restore '{snapshot_name}' failed: {e}")
            return False

    def delete_sandbox(self) -> bool:
        """Clean up and delete the sandbox computer idempotently."""
        if self.is_deleted:
            return True
        if not self.computer:
            self.is_deleted = True
            return True

        try:
            if hasattr(self.computer, "delete"):
                self.computer.delete()
            self.is_deleted = True
            self.is_ready = False
            logger.info(f"Deleted Celesto computer '{self.sandbox_name}'")
            return True
        except Exception as e:
            self.cleanup_error = str(e)
            logger.error(f"Error during sandbox cleanup for '{self.sandbox_name}': {e}")
            # Mark deleted to avoid re-triggering broken references
            self.is_deleted = True
            return False

    def get_status(self) -> dict[str, Any]:
        """Return provider status and diagnostic metrics."""
        return {
            "provider": "celesto",
            "provider_mode": self.provider_mode,
            "sandbox_name": self.sandbox_name,
            "boot_to_ready_s": self.boot_to_ready_s,
            "is_ready": self.is_ready,
            "is_deleted": self.is_deleted,
            "cleanup_error": self.cleanup_error,
            "snapshots": list(self.snapshots.keys()),
        }
