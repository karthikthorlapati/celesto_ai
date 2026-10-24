"""Base provider interface for Celesto sandbox execution."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ProviderCommandResult:
    """Standard command execution result returned by all sandbox providers."""
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float = 0.0

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    @property
    def output(self) -> str:
        return (self.stdout or "").strip()


class SandboxProvider(ABC):
    """Abstract interface defining required sandbox lifecycle and execution capabilities."""

    @abstractmethod
    def create_sandbox(self, name: str, **kwargs: Any) -> str:
        """Create a uniquely named sandbox. Returns sandbox ID / name."""
        pass

    @abstractmethod
    def wait_until_ready(self, timeout_s: float = 30.0) -> float:
        """Wait for the guest computer to become ready.

        Returns boot-to-ready time in seconds.
        """
        pass

    @abstractmethod
    def execute_command(self, command: str, timeout_s: int = 30) -> ProviderCommandResult:
        """Execute a command inside the guest computer.

        CRITICAL: All task commands must execute inside the sandbox, never on the host.
        """
        pass

    @abstractmethod
    def delete_sandbox(self) -> bool:
        """Clean up and delete the sandbox. Must be idempotent."""
        pass

    @abstractmethod
    def snapshot(self, snapshot_name: str) -> bool:
        """Create a checkpoint/snapshot of current sandbox state if supported."""
        pass

    @abstractmethod
    def restore(self, snapshot_name: str) -> bool:
        """Restore sandbox state from a previously saved checkpoint if supported."""
        pass

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        """Return provider status, timing, and cleanup information."""
        pass
