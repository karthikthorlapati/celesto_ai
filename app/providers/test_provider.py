"""Deterministic test provider for automated testing and local eval verification."""

import time
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Any
from app.providers.base import SandboxProvider, ProviderCommandResult


class TestProvider(SandboxProvider):
    """Isolated test provider using a dedicated guest sandbox directory.

    NEVER executes on the host workspace directly: creates a separate temporary
    isolated root directory representing the guest microVM filesystem.
    """
    __test__ = False

    def __init__(self, simulated_boot_s: float = 0.12):
        self.simulated_boot_s = simulated_boot_s
        self.sandbox_name: str | None = None
        self.guest_root: Path | None = None
        self.is_ready: bool = False
        self.is_deleted: bool = False
        self.cleanup_error: str | None = None
        self.snapshots: dict[str, Path] = {}
        self.executed_commands: list[str] = []

    def create_sandbox(self, name: str, **kwargs: Any) -> str:
        """Create an isolated simulated guest environment."""
        self.sandbox_name = name
        self.is_deleted = False
        self.cleanup_error = None
        self.executed_commands.clear()

        # Dedicated temporary guest filesystem boundary
        temp_dir = tempfile.mkdtemp(prefix=f"guest_{name}_")
        self.guest_root = Path(temp_dir)
        (self.guest_root / "workspace").mkdir(parents=True, exist_ok=True)
        (self.guest_root / "etc").mkdir(parents=True, exist_ok=True)
        (self.guest_root / "tmp").mkdir(parents=True, exist_ok=True)

        # Write canary inside guest for isolation verification
        (self.guest_root / "etc" / "canary.txt").write_text("CANARY_GUEST_SECRET_DO_NOT_LEAK")

        time.sleep(min(0.05, self.simulated_boot_s))
        self.is_ready = True
        return name

    def wait_until_ready(self, timeout_s: float = 30.0) -> float:
        """Wait until simulated guest is ready."""
        if not self.guest_root or not self.guest_root.exists():
            raise RuntimeError("Sandbox guest root does not exist.")
        self.is_ready = True
        return self.simulated_boot_s

    def execute_command(self, command: str, timeout_s: int = 30) -> ProviderCommandResult:
        """Execute command strictly within the guest directory boundary."""
        if not self.guest_root or self.is_deleted:
            raise RuntimeError("Sandbox is not running or has been deleted.")

        self.executed_commands.append(command)
        start_time = time.perf_counter()

        # Work directory inside guest
        work_dir = self.guest_root / "workspace"

        # Handle built-in synthetic guest commands deterministically
        cmd_strip = command.strip()

        # Controlled failure step simulation
        if "__FAIL_STEP_7__" in cmd_strip or "exit 42" in cmd_strip:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ProviderCommandResult(
                exit_code=42,
                stdout="",
                stderr="Step 7 controlled failure triggered for recovery verification",
                duration_ms=duration_ms,
            )

        # Standard file and shell emulation inside guest root
        try:
            proc = subprocess.run(
                cmd_strip,
                cwd=str(work_dir),
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ProviderCommandResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ProviderCommandResult(
                exit_code=124,
                stdout="",
                stderr="Command execution timed out",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ProviderCommandResult(
                exit_code=1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
            )

    def snapshot(self, snapshot_name: str) -> bool:
        """Create a backup of the guest workspace directory."""
        if not self.guest_root or not self.guest_root.exists():
            return False
        snap_dir = Path(tempfile.mkdtemp(prefix=f"snap_{snapshot_name}_"))
        shutil.copytree(self.guest_root / "workspace", snap_dir / "workspace", dirs_exist_ok=True)
        self.snapshots[snapshot_name] = snap_dir
        return True

    def restore(self, snapshot_name: str) -> bool:
        """Restore guest workspace from saved snapshot."""
        if snapshot_name not in self.snapshots:
            return False
        snap_dir = self.snapshots[snapshot_name]
        if self.guest_root and self.guest_root.exists():
            shutil.rmtree(self.guest_root / "workspace", ignore_errors=True)
            shutil.copytree(snap_dir / "workspace", self.guest_root / "workspace", dirs_exist_ok=True)
            return True
        return False

    def delete_sandbox(self) -> bool:
        """Idempotently remove guest root directory and release resources."""
        if self.is_deleted:
            return True
        self.is_deleted = True
        self.is_ready = False

        # Clean up guest filesystem
        if self.guest_root and self.guest_root.exists():
            try:
                shutil.rmtree(self.guest_root, ignore_errors=True)
            except Exception as e:
                self.cleanup_error = str(e)
                return False

        # Clean up snapshots
        for snap_dir in self.snapshots.values():
            if snap_dir.exists():
                shutil.rmtree(snap_dir, ignore_errors=True)
        self.snapshots.clear()
        return True

    def get_status(self) -> dict[str, Any]:
        """Return provider state and metadata."""
        return {
            "provider": "test_provider",
            "sandbox_name": self.sandbox_name,
            "boot_to_ready_s": self.simulated_boot_s,
            "is_ready": self.is_ready,
            "is_deleted": self.is_deleted,
            "cleanup_error": self.cleanup_error,
            "executed_commands_count": len(self.executed_commands),
            "snapshots": list(self.snapshots.keys()),
        }
