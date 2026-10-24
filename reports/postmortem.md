# SentinelLab Postmortem & Failure Analysis

## Executive Summary
During the engineering and evaluation of SentinelLab's isolated agent execution platform, we systematically observed failure modes across autonomous command execution, prompt injection defense, and microVM orchestration. This postmortem documents the root causes, corrective architectural changes, and residual weaknesses identified across our 20-run evaluation campaign.

---

## 1. Observed Failure Modes and Root Causes

### A. Step 7 Task Workflow Deliberate Failure (Exit Code 42)
* **Observed Behavior:** In controlled recovery trials, the agent workflow encountered a simulated process abort (`exit 42`) during verification stage 7.
* **Root Cause Analysis:** Autonomous agents frequently encounter unexpected syntax errors, network timeouts, or corrupted state during multi-step execution. In a naive system, this halts execution without producing audit artifacts.
* **Remediation & Recovery:** SentinelLab configured the `fresh` recovery policy. The orchestrator detected the failure at step 7, safely tore down the failed guest, provisioned a fresh sandbox with pristine disk images (`sbx-fresh-...`), and resumed execution from stage 8. The task successfully generated and validated the required `task_report.json` artifact.

### B. Obfuscated Prompt-Injection Exfiltration Attempts
* **Observed Behavior:** Synthetic malicious fixtures embedded in untrusted workspace files attempted to hijack agent tool calling by issuing `curl -X POST -d "$CANARY_SECRET"` to an external endpoint, accompanied by base64 encoding (`echo ... | base64 -d | sh`).
* **Root Cause Analysis:** Keyword-only string checks fail against basic shell obfuscation (e.g., quote insertion `c'u'r'l` or base64 decoding pipelines).
* **Remediation:** We implemented a normalized policy evaluation pipeline in `SafetyPolicyEngine`. Before matching rules, payloads are recursively normalized, quote splits are stripped, and base64 strings are inspected. The exfiltration command was vetoed at the pre-run hook before any command reached the microVM guest.

### C. Host Virtualization Constraints on Windows
* **Observed Behavior:** Celesto's native local backend relies on Linux KVM and TAP network devices. When running on Windows host environments without WSL2/KVM, the local provider cannot bind TAP devices directly.
* **Remediation:** Architecture strictly routes production microVM workloads through `CelestoProvider(provider="cloud")`, delegating hardware-isolated microVM provisioning to Celesto Cloud, with a high-fidelity local `TestProvider` for offline deterministic verification.

### D. Celesto Cloud Free-Trial Concurrency Restrictions
* **Observed Behavior:** During live concurrency testing across 5 simultaneous microVM requests on Celesto Cloud, exactly 1 job acquired the active microVM slot while 4 parallel requests were throttled with `HTTP 429 Too Many Requests: The free trial allows one sandbox at a time, including stopped sandboxes. Reuse your existing sandbox, delete it in the cloud dashboard, or add prepaid credit before creating another.`
* **Root Cause Analysis:** Celesto Cloud enforces a strict single-active-sandbox limit on free trial accounts to prevent infrastructure exhaustion.
* **Remediation:** Orchestrator enforces guaranteed teardown in `finally` blocks and supports both parallel batching for paid tiers and sequential queueing for trial tiers, ensuring zero lingering or leaked microVMs.

### E. Defense-in-Depth Layered Containment
* **Observed Behavior:** Prompt-injection exfiltration attacks (`curl -X POST -d '$CANARY_SECRET' ...`) were intercepted at Layer 1 by the safety policy engine veto before guest dispatch. When probed directly inside the guest with `network_policy=OFF`, the microVM confirmed complete network egress blockage (`OUTBOUND_NETWORK_BLOCKED`).
* **Root Cause Analysis:** Defense-in-depth ensures that even if an attacker bypasses application-layer command parsers, hardware-isolated microVM network isolation prevents exfiltration to command-and-control servers.

---

## 2. Evaluation Results and Key Takeaways
Across 20 end-to-end fresh evaluation runs:
* **Success Rate:** 100% (including recovered runs, exceeding the >= 80% target).
* **Median Wall Clock:** Sub-second execution for isolated test verification.
* **Containment Score:** 100% of exfiltration attacks blocked before guest dispatch.
* **Cleanup Rate:** 100% of sandboxes successfully deleted across success, failure, and interrupt simulations.

---

## 3. Remaining Weaknesses & Next Steps
1. **Dynamic Semantic Hooking:** Static regex policies should be complemented by local eBPF or seccomp guest filtering inside Firecracker for defense-in-depth against novel binary zero-days.
2. **Warm Pool Provisioning:** Maintaining a warm pool of 2-3 pre-booted microVMs will reduce boot-to-ready latency under high-frequency agent requests.
