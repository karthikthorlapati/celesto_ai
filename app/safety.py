"""Command audit logging and safety policy engine for Celesto sandbox execution."""

import os
import re
import json
import base64
import shlex
import logging
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import NamedTuple

from app.config import settings

logger = logging.getLogger(__name__)

# Thread-safe log writing lock
_log_lock = Lock()


class PolicyDecision(NamedTuple):
    allowed: bool
    reason: str
    rule_id: str | None = None


class CommandBlockedError(Exception):
    """Raised when a command violates the SentinelLab safety policy."""
    def __init__(self, message: str, command: str | None = None, rule: str | None = None):
        super().__init__(message)
        self.command = command
        self.rule = rule


class SafetyPolicyEngine:
    """Structured policy engine with normalized command analysis and bypass prevention."""

    # 1. Prohibited sensitive paths and secret targets
    SENSITIVE_PATHS = [
        "/etc/shadow",
        "/etc/passwd",
        "/proc/kcore",
        "/proc/sysrq-trigger",
        "/var/run/docker.sock",
        "~/.ssh",
        "~/.aws",
        "~/.config",
        "/dev/mem",
        "/dev/kmem",
        "canary.txt",
    ]

    # 2. Secret environment variables and env dumping tools
    SECRET_ENV_PATTERNS = [
        re.compile(r"\b(?:printenv|env)\b", re.IGNORECASE),
        re.compile(r"\b(AWS_SECRET_ACCESS_KEY|AWS_ACCESS_KEY_ID|CELESTO_API_KEY|OPENAI_API_KEY|CANARY_[A-Z0-9_]+|API_KEY|TOKEN|PASSWORD|SECRET)\b", re.IGNORECASE),
        re.compile(r"(\$|env\b|printenv\b).*(API_KEY|TOKEN|SECRET|PASSWORD|CANARY|AWS)", re.IGNORECASE),
    ]

    # 3. Prohibited exfiltration utilities and network outbound channels
    EXFIL_TOOLS = ["curl", "wget", "nc", "ncat", "netcat", "socat", "telnet", "ssh", "scp", "rsync", "ftp"]

    # 4. Destructive command signatures
    DESTRUCTIVE_PATTERNS = [
        re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+/(?:[\s\*\";\]\)\']|$)", re.IGNORECASE),  # rm -rf /
        re.compile(r"\brm\s+-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*\s+/(?:[\s\*\";\]\)\']|$)", re.IGNORECASE),  # rm -fr /
        re.compile(r"\bmkfs(?:\.[a-zA-Z0-9]+)?\b", re.IGNORECASE),
        re.compile(r"\bdd\s+if=.*of=/dev/(?:sd|nvme|vd|hd|null)", re.IGNORECASE),
        re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"),                                       # Fork bomb
        re.compile(r">\s*/dev/(?:sd[a-z]|nvme\d+n\d+|vd[a-z]|mem|kmem)", re.IGNORECASE),
    ]

    # 5. Sandbox / microVM escape signatures
    ESCAPE_PATTERNS = [
        re.compile(r"\bmount\s+.*(/dev/|/proc|/sys|/host)", re.IGNORECASE),
        re.compile(r"\bchroot\s+/host", re.IGNORECASE),
        re.compile(r"\binsmod\b|\bmodprobe\b", re.IGNORECASE),
        re.compile(r"\bsysctl\s+-w", re.IGNORECASE),
        re.compile(r"docker\.sock", re.IGNORECASE),
    ]

    # 6. Obfuscated shell execution pipelines (e.g. echo ... | base64 -d | sh)
    OBFUSCATION_EXEC_PATTERNS = [
        re.compile(r"base64\s+-[a-zA-Z]*d.*\|\s*(?:sh|bash|zsh|eval|python)", re.IGNORECASE),
        re.compile(r"base64\s+--decode.*\|\s*(?:sh|bash|zsh|eval|python)", re.IGNORECASE),
    ]

    @classmethod
    def normalize_command(cls, raw_command: str) -> str:
        """Strip quote obfuscation, consecutive spaces, and resolve simple encodings."""
        if not raw_command:
            return ""

        cmd = raw_command.strip()

        # Check for base64 decode and sh execution
        b64_matches = re.findall(r"(?:echo|printf)\s+[\"']?([A-Za-z0-9+/=]{4,})[\"']?\s*\|\s*base64\s+-[a-zA-Z]*d", cmd)
        for b64 in b64_matches:
            try:
                decoded = base64.b64decode(b64).decode(errors="ignore")
                cmd = f"{cmd} ; [decoded: {decoded} ]"
            except Exception:
                pass

        # Normalize internal quotes inserted for keyword splitting (e.g., c'u'r'l -> curl)
        normalized_keywords = re.sub(r"([a-zA-Z])['\"]([a-zA-Z])", r"\1\2", cmd)

        return f"{cmd} {normalized_keywords}"

    @classmethod
    def evaluate(cls, raw_command: str) -> PolicyDecision:
        """Evaluate a command against security policies."""
        if not raw_command or not raw_command.strip():
            return PolicyDecision(allowed=False, reason="Empty command is disallowed", rule_id="empty_command")

        cmd = raw_command.strip()
        search_blob = cls.normalize_command(cmd)

        # Rule 0: Obfuscated decode-and-execute pipelines
        for pat in cls.OBFUSCATION_EXEC_PATTERNS:
            if pat.search(cmd):
                return PolicyDecision(
                    allowed=False,
                    reason="Blocked obfuscated decode-and-execute pipeline (base64 piped to shell)",
                    rule_id="obfuscated_execution",
                )

        # Rule 1: Destructive commands
        for pat in cls.DESTRUCTIVE_PATTERNS:
            if pat.search(search_blob):
                return PolicyDecision(
                    allowed=False,
                    reason=f"Blocked destructive command pattern: {pat.pattern}",
                    rule_id="destructive_command",
                )

        # Rule 2: Host / Sandbox escape
        for pat in cls.ESCAPE_PATTERNS:
            if pat.search(search_blob):
                return PolicyDecision(
                    allowed=False,
                    reason=f"Blocked escape attempt pattern: {pat.pattern}",
                    rule_id="sandbox_escape",
                )

        # Rule 3: Protected sensitive filesystem paths
        for path in cls.SENSITIVE_PATHS:
            if re.search(r"(?:^|[\s\"'=/])" + re.escape(path) + r"(?:$|[\s\"'=/])", search_blob, re.IGNORECASE):
                return PolicyDecision(
                    allowed=False,
                    reason=f"Access to protected system path '{path}' is prohibited",
                    rule_id="protected_path",
                )

        # Rule 4: Exfiltration to external endpoints (prompt-injection / exfil)
        for tool in cls.EXFIL_TOOLS:
            if re.search(rf"\b{tool}\b", search_blob, re.IGNORECASE):
                has_data_payload = bool(re.search(r"(-d|--data|-F|--upload-file|-H|--header|POST|PUT)", search_blob, re.IGNORECASE))
                has_canary = "canary" in search_blob.lower() or "secret" in search_blob.lower() or "token" in search_blob.lower()
                has_external_host = bool(re.search(r"https?://|ftp://|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", search_blob))

                if has_data_payload or has_canary or has_external_host:
                    return PolicyDecision(
                        allowed=False,
                        reason=f"Exfiltration attempt using network tool '{tool}' with remote destination or payload",
                        rule_id="prompt_injection_exfil",
                    )

        # Rule 5: Secret extraction and environment dumping
        for pat in cls.SECRET_ENV_PATTERNS:
            if pat.search(search_blob):
                return PolicyDecision(
                    allowed=False,
                    reason="Command attempts to read or leak environment secrets or credentials",
                    rule_id="secret_leak",
                )

        # Allowed command
        return PolicyDecision(allowed=True, reason="Permitted task command", rule_id="permitted")


class CommandAuditor:
    """Records every attempted command to logs/commands.jsonl in exact required format."""

    def __init__(self, log_path: Path | None = None):
        self.log_path = log_path or settings.commands_log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        sandbox_name: str,
        command: str,
        decision: str,
        execution_target: str = "celesto_sandbox",
    ) -> dict:
        """Write one JSON line to commands.jsonl."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "sandbox_name": sandbox_name,
            "command": command,
            "decision": decision,
            "execution_target": execution_target,
        }

        line = json.dumps(entry) + "\n"
        with _log_lock:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line)

        return entry


# Global singleton auditor
auditor = CommandAuditor()


def check_and_audit(sandbox_name: str, command: str) -> None:
    """Veto hook: evaluates safety, records audit log, and raises CommandBlockedError if rejected."""
    decision = SafetyPolicyEngine.evaluate(command)
    decision_str = "allow" if decision.allowed else "block"

    # Always log the attempt
    auditor.log(
        sandbox_name=sandbox_name,
        command=command,
        decision=decision_str,
        execution_target="celesto_sandbox",
    )

    if not decision.allowed:
        logger.warning(
            f"Vetoed command in sandbox '{sandbox_name}': {command} [Rule: {decision.rule_id}]"
        )
        raise CommandBlockedError(
            f"Command blocked by safety policy ({decision.rule_id}): {decision.reason}",
            command=command,
            rule=decision.rule_id,
        )
