# ⚡ LiveResponse — Autonomous Out-of-Band Incident Responder

**Live Response** (formerly Super SOAR) is an autonomous, out-of-band **Security Orchestration, Automation, and Response (SOAR)** platform engineered to protect critical infrastructure, production servers, and web applications.

It operates strictly on an **isolated management server/VM**, monitoring incoming security telemetry and dispatching precision containment actions against compromised targets without depending on the compromised machine's resources.

---

## 🌟 Key Capabilities

- **Out-of-Band Isolation**: SOAR runs on a dedicated management VM/network; if the production web application or database is breached, the responder remains secure, armed, and uncompromised.
- **Plug & Play Web Console ("Click & Voila")**: Modern, cyberpunk SOC dashboard with ready-to-run incident response scenario templates. Test, simulate, and trigger containment with a single click.
- **Zero-Trust Go Proxy Agent**: Includes a high-performance compiled Go proxy agent with **HMAC-SHA256 request authentication** and a strict tactical command allowlist.
- **Agentless SSH Fallback**: Executes tactical containment over remote SSH key authentication via `paramiko`.
- **Pre-Built Attack Defense Playbooks**:
  - 🛡️ **PHP2Shell & Web Shell Defense**: Quarantines rogue PHP payloads, revokes file permissions (`chmod 000`), terminates rogue PHP-FPM / reverse-shell child workers, and blocks attacker IPs.
  - 🌊 **DDoS Containment**: Activates kernel SYN cookies, enforces L4/L7 `iptables` rate limits, and triggers external Cloudflare / firewall APIs.
  - 🔑 **SSH Brute-Force Response**: Auto-enriches attacker IPs via threat intelligence, prompts for analyst 1-click approval, and drops attacker packets.
  - 🔒 **Ransomware Host Isolation**: Instantly severs network interfaces (`ip link set down`) to prevent lateral spread, freezes high-IO encryptor processes, and flags host for quarantine.
  - 👤 **Privilege Escalation Containment**: Kills unauthorized user sessions (`pkill -KILL -u`), locks accounts (`usermod -L`), and revokes sudo credentials.
  - 💉 **SQL Injection & DB Defense**: Drops attacking IPs and terminates suspicious database threads.
- **Fail-Safe Safety Guardrails**:
  - **Immutable Whitelist**: Never isolates gateways, loopbacks, DNS, or configured SOC subnets.
  - **Dry-Run Mode**: Test and simulate playbooks without altering production state.
  - **Approval Gates**: Sensitive actions pause and wait for analyst authorization in the Web UI or Slack.
  - **Reverse Rollback**: Automatically runs undo actions in reverse order if any containment step fails.
  - **Tamper-Resistant Audit Trail**: Append-only `audit.jsonl` log enforced by `os.fsync`.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 MANAGEMENT VM (Out-of-Band)                 │
│                                                             │
│   ┌──────────────┐     ┌──────────────┐    ┌────────────┐   │
│   │ Alert Ingest │───▶ │   Playbook   │───▶│ Execution  │   │
│   │  (Webhooks/  │     │    Engine    │    │  Workers   │   │
│   │  UI Voila!)  │     │   (Python)   │    │            │   │
│   └──────────────┘     └──────────────┘    └─────┬──────┘   │
│          ▲                    ▲                  │          │
│          │                    │                  ▼          │
│   ┌──────────────┐     ┌──────────────┐    ┌────────────┐   │
│   │ Plug & Play  │     │  Safety &    │    │ State DB & │   │
│   │ Web Console  │     │  Whitelist   │    │ Fsync Log  │   │
│   └──────────────┘     └──────────────┘    └────────────┘   │
└───────────────────────────────┬─────────────────────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Production Node  │  │ Production Host  │  │ External APIs    │
│   (SSH Direct)   │  │ (Go Proxy Agent) │  │ (Cloudflare/     │
│                  │  │ (HMAC Protected) │  │ VirusTotal/Slack)│
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## 🚀 Quick Start

### One-Click Download (Click and Run)

Prebuilt, ready-to-run binaries ship in this repository — no Python, no build step:

| File | Platform | How to use |
| :--- | :--- | :--- |
| `LiveResponse.exe` | Windows | Download, place next to `config/` & `playbooks/` (or the whole repo), double-click. Server starts and the console opens in your browser. |
| `live-response` (built via CI) | Linux | Run the `build-binaries` workflow or `./scripts/build_exe.sh`; then `./live-response`. |
| `var/bin/super-agent.exe` | Production host (Windows) | Compiled Go proxy agent; see section below. |
| `var/bin/super-agent` | Production host (Linux) | Compiled Go proxy agent; `chmod +x` then run. |

Console URL after launch: `http://localhost:8088`

### Build From Source

#### On Linux / macOS / Management VM

```bash
# 1. Run automated installer
./scripts/install.sh

# 2. Launch Live Response
./scripts/run.sh
```

#### On Windows

```powershell
# 1. Run PowerShell installer
.\scripts\install.ps1

# 2. Launch or build the runtime
.\scripts\run.ps1            # run from source
.\scripts\build_exe.ps1      # build LiveResponse.exe
```


Access the interactive dashboard in your browser:
👉 **`http://localhost:8088`**

---

## 🎯 "Click and Voila" Incident Response Scenarios

The web console provides ready-made, click-to-run defense plugins for the most prevalent real-world attacks:

| Scenario Plugin | Target Threat | Primary Automated Response |
| :--- | :--- | :--- |
| **`php2shell_webshell_defense`** | PHP Backdoors / CGI RCE / Webshells | `chmod 000`, `/var/quarantine/`, `pkill -9 php-fpm`, `iptables DROP` |
| **`ddos_flood_mitigation`** | Layer 4 SYN/UDP & L7 HTTP Flood | `net.ipv4.tcp_syncookies=1`, connection rate limiting, Cloudflare API |
| **`ssh_brute_force_response`** | Credential Stuffing / SSH Brute Force | Threat intel enrichment, 1-click Approval Gate, `iptables DROP` |
| **`ransomware_isolation`** | High-IO file encryption / Canary alert | `ip link set eth0 down`, freeze encryptor PID, forensic snapshot |
| **`privilege_escalation_containment`** | Rogue sudoers tampering / shadow edit | `pkill -KILL -u user`, `usermod -L`, revoke sudo tokens |
| **`sql_injection_containment`** | Automated SQLMap / Data exfiltration | Attacker IP drop, terminate rogue database connection threads |

---

## 🤖 The Compiled Go Agent (Zero-Trust Model)

On hardened production servers where SSH is restricted, deploy the compiled Go proxy agent:

```bash
# Set shared HMAC secret key
export SOAR_AGENT_KEY="your-32-byte-hex-key"

# Run agent on production host
./var/bin/super-agent
# Listening on 127.0.0.1:8099
```

- Every request from the management SOAR is signed with `X-Soar-Signature: HMAC-SHA256(payload, SOAR_AGENT_KEY)`.
- Even if the SOAR management VM were compromised, the Go agent only allows commands starting with pre-approved security prefixes (`iptables `, `chmod 000 `, `pkill `, etc.) and rejects arbitrary code execution.

---

## ⚙️ REST & Webhook Ingestion API

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `GET` | `/` | Open the interactive Web Dashboard |
| `POST` | `/webhook/wazuh` | Receive real-time alerts from Wazuh SIEM |
| `POST` | `/webhook/suricata` | Receive IDS alerts from Suricata / Snort |
| `POST` | `/api/playbooks/{name}/trigger` | 1-Click trigger / simulate a scenario |
| `GET` | `/api/approvals/pending` | List actions waiting for analyst sign-off |
| `POST` | `/api/approvals/{id}/approve` | Authorize a gated action |
| `POST` | `/api/approvals/{id}/reject` | Reject a gated action |
| `GET` | `/api/executions` | Fetch recent incident executions and action outputs |
| `GET` | `/api/audit` | Inspect the fsync-enforced JSONL audit trail |
| `POST` | `/api/config/dry_run` | Toggle between Dry-Run Simulation and Live Mode |

---

## 🛡️ License & Ethics

Designed exclusively for defensive security operations, automated SOC incident response, and authorized server management.
