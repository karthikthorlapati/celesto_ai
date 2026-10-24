"""Automated tests for sandbox lifecycle and guaranteed cleanup."""

import pytest
from unittest.mock import MagicMock
from app.orchestrator import RunOrchestrator, generate_sandbox_name
from app.providers.test_provider import TestProvider


def test_sandbox_name_format_and_uniqueness():
    """Verify generated sandbox names conform to ^sbx-[a-z0-9]{8,}$ and are unique."""
    names = [generate_sandbox_name() for _ in range(50)]
    assert len(set(names)) == 50
    for name in names:
        assert name.startswith("sbx-")
        suffix = name.split("sbx-")[1]
        assert len(suffix) >= 8
        assert suffix.isalnum()
        assert suffix == suffix.lower()


def test_cleanup_on_success():
    """Verify sandbox cleanup is invoked upon successful workflow completion."""
    provider = TestProvider()
    orchestrator = RunOrchestrator(provider=provider)

    res = orchestrator.run_task(trigger_step7_failure=False)
    assert res["success"] is True
    assert res["cleanup_performed"] is True
    assert res["cleanup_success"] is True
    assert provider.is_deleted is True


def test_cleanup_on_failure():
    """Verify sandbox cleanup is invoked even when workflow encounters an unhandled failure."""
    provider = TestProvider()
    orchestrator = RunOrchestrator(provider=provider, default_policy="resume")

    # Simulate step 1 failure
    provider.create_sandbox = MagicMock(side_effect=RuntimeError("Guest crash"))
    res = orchestrator.run_task()

    assert res["success"] is False
    assert res["cleanup_performed"] is True
    assert provider.is_deleted is True


def test_cleanup_on_interruption():
    """Verify sandbox cleanup is attempted when KeyboardInterrupt is received."""
    provider = TestProvider()
    orchestrator = RunOrchestrator(provider=provider)

    # Mock execute_command to simulate Ctrl-C interrupt
    provider.execute_command = MagicMock(side_effect=KeyboardInterrupt("Simulated Ctrl-C"))

    with pytest.raises(KeyboardInterrupt):
        orchestrator.run_task(trigger_step7_failure=False)

    # Cleanup must be executed
    assert provider.is_deleted is True


def test_cleanup_failure_recorded():
    """Verify that cleanup failure does not get silently hidden, but is recorded."""
    provider = TestProvider()
    # Mock delete_sandbox to fail
    provider.delete_sandbox = MagicMock(side_effect=RuntimeError("Docker daemon connection lost"))

    orchestrator = RunOrchestrator(provider=provider)
    res = orchestrator.run_task(trigger_step7_failure=False)

    assert res["cleanup_performed"] is True
    assert res["cleanup_success"] is False
    assert "Docker daemon connection lost" in str(res["cleanup_error"])
