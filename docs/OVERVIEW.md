# Live Response — Platform Documentation

**Live Response** is an out-of-band Security Orchestration, Automation, and Response (SOAR) platform. It runs on an isolated management server or VM, consumes security telemetry from SIEMs, IDSes and webhooks, and automatically dispatches precision containment actions against production hosts — without depending on a compromised machine for its own defense.

## 1. How It Works

Live Response follows one pipeline: **Ingest → Match → Execute → Audit**.

```
┌─────────────────────────────────────────────────────────────┐
│                 MANAGEMENT VM (Out-of-Band)                 │
│                                                             │
│  Alert Ingest ──▶ Playbook Engine ──▶ Execution Workers     │
│                                                │            │
│  Web Console (this dashboard)                  │            │
│  Safety & Whitelist Guardrail                  ▼            │
│  State DB (aiosqlite) + fsync JSONL Audit Trail             │
└──────────────────────────┬──────────────────────────────────┘
                           │
    ┌──────────────────────┼──────────────────────┐
    ▼                      ▼                      ▼
 SSH (paramiko)    Zero-Trust Go Agent    External APIs
 (agentless            (HMAC-SHA256        (Cloudflare,
  fallback)            signed HTTP)        VirusTotal, Slack)
```

### 1.1 Alert Ingestion

Alerts arrive by webhook: `/webhook/wazuh` for the Wazuh SIEM, `/webhook/suricata` for IDS events, or any custom source. Each alert payload is normalized into a common `Alert` model — source, severity, attacker IP, target host/name, suspect file path — so playbooks never depend on vendor-specific field layouts. Analysts can also trigger scenarios manually from the dashboard, which constructs the same normalized alert.

### 1.2 Playbook Engine

Playbooks are declarative YAML specs (or type-checked Python, built in the dashboard's Custom Playbook Builder). Each playbook contains:

- `trigger` — the alert profile it responds to (source, category, rule ID, severity, any combination of)
- `conditions` — field-level matching using operators such as `eq`, `contains`, `exists`, and `not_in_whitelist`
- `actions` — the ordered containment sequence
- `rollback` — compensation actions, executed in **reverse order automatically** if any containment step fails

A Jinja2 templating layer injects live alert fields and configured secrets into every action parameter (for example `chmod 000 {{ alert.file_path }}`), and a global rate limiter caps actions per hour to contain blast radius on alert storms.

### 1.3 Action Executors

Every action type is a small, interchangeable executor:

| Executor | Purpose | Transport |
| :--- | :--- | :--- |
| `ssh` | Agentless containment over SSH key authentication | paramiko |
| `agent` | Commands through the compiled Go proxy agent with pre-approved command prefixes | HMAC-signed HTTP |
| `web3` | On-chain emergency pause, revoke, blacklist, or rescue on EVM chains | JSON-RPC |
| `http` | Calls external protection APIs (for example Cloudflare/firewall services) | HTTPS |
| `local` | Actions on the management VM itself | subprocess |
| `approval` | Pauses the playbook until an analyst signs off in the dashboard or Slack | internal + Slack |
| `tunnel` | Opens or closes the encrypted management tunnel (Cloudflare WARP) | warp-cli |

### 1.4 The Zero-Trust Go Agent

On hardened servers where SSH is closed, the bundled Go agent listens locally and only accepts requests signed with `X-Soar-Signature: HMAC-SHA256(payload, key)`. Even a fully compromised management plane can only issue commands from a strict tactical allowlist (`iptables`, `chmod 000`, `pkill`, and similar security prefixes); arbitrary code execution is structurally impossible through the agent.

## 2. Safety Model

Automated containment is dangerous; the whole design is aimed at making one mistake survivable.

- **Out-of-band deployment**: the responder lives on a dedicated management VM. If the production host falls, the defender does not.
- **Immutable whitelist**: gateway, loopback, DNS, and configured SOC subnets are never isolated. The engine refuses SSH/agent commands targeting any whitelisted address, no matter what a playbook asks.
- **Dry-run by default every boot**: playbooks run in simulation, producing a complete action trace without touching the host. Going live is an explicit, single-click, analyst-controlled flip.
- **Approval gates**: flagged actions pause for human sign-off before executing — dashboard button or Slack, with an audit trail for who approved what.
- **Reverse rollback**: if a sequence breaks halfway (for example, step 3 of 4 fails), steps already taken are compensated in reverse order; no half-closed incident state.
- **Tamper-resistant audit trail**: a JSONL execution log appended to disk with `os.fsync` enforcement on every write.

## 3. Encrypted Networking (Cloudflare WARP)

The `tunnel` executor and dashboard **Up/Down** control establish an encrypted Cloudflare WARP transport from the management server. Use it to secure management traffic crossing untrusted networks, or to reach protected nodes over an encrypted route. Requirements: the Cloudflare WARP client installed on the management server (`warp-cli` on PATH, or the standard Windows install location). Operation status is surfaced in the header chip (SECURED / CLOSED) and audited like any other action.

## 4. Integration Keys (Bring Your Own Keys)

The **Settings** dialog accepts the operator's own tokens — Cloudflare API token and zone ID, VirusTotal, AbuseIPDB, Slack webhook — and stores them locally in `config/secrets.local.yaml` (never committed). Local values override environment variables at load; values are masked in the dashboard and usable inside playbook templates as `{{ secrets.vt_api_key }}`.

## 5. The Web Console

A retro-professional dashboard (Windows 95/XP/7 style, white and red identity) covering:

- **Ready-to-use scenarios** — one-click simulate/execute for each playbook
- **Armed-mode indicator and dry-run switch** — simulate vs. live production execution
- **Pending-approval triage** — approve or reject gated actions inline
- **Execution history drilldown** — per-action pass/fail, output, duration, simulation marker
- **Fsync audit feed** — the live, append-only trail
- **Custom Playbook Builder** — author typed Python playbooks in the browser, compile and hot-deploy without restarting

## 6. Running It

- **End user (click and run):** place `run.py` next to the project, build once with `scripts/build_exe.ps1` (Windows) or `build_exe.sh` (Linux), then double-click `LiveResponse.exe` / `live-response`. The server starts on `localhost:8088` and the console opens automatically.
- **Developer:** `python -m soar` after installing requirements (`pip install -r requirements.txt`); useful flags: `--port`, `--live`, `--open-browser`.

## 7. Use Cases

1. **Web shell / PHP backdoor response** — an upload path gets RCE'd; the platform quarantines the payload (`chmod 000` → `/var/quarantine`), kills rogue PHP-FPM children, and drops the attacker's IP, all in one click.
2. **DDoS containment** — SYN-flood or HTTP-flood detected: SYN cookies on, connection-rate limits enforced via iptables, and an external Cloudflare/API "under attack" flip.
3. **SSH brute-force response** — the attacker's IP is enriched through threat intel (VirusTotal/AbuseIPDB, keys via Settings), an analyst approves with one click, packets routed to `/dev/null`.
4. **Ransomware isolation** — canary file activity or high-IO encryptor observed on host: the host's network interface is severed immediately to stop lateral movement, and processes are frozen for forensics.
5. **Privilege-escalation containment** — rogue sessions killed, the compromised account locked, sudo credentials revoked.
6. **SQL injection containment** — attacking IPs dropped, suspicious DB connection threads terminated.
7. **Smart-contract incident response** — on-chain exploit detected: emergency pause or transfer-rescue invoked against the EVM contract, optionally gated by analyst approval first.
8. **Notification-driven on-call** — Slack webhooks wake the on-call analyst for approval-gated actions; they sign off from the dashboard or Slack within the configured timeout.

## 8. Quick API Reference

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| GET | `/` | Web dashboard |
| GET | `/health`, `/api/stats` | Health and live metrics |
| POST | `/webhook/{source}` | SIEM/IDS alert ingestion |
| GET | `/api/playbooks` | Loaded playbook catalog |
| POST | `/api/playbooks/{name}/trigger` | Simulate or execute a scenario |
| GET / POST | `/api/secrets` | Integration keys (masked / write) |
| GET | `/api/tunnel/status`, POST `/api/tunnel/{op}` | Encrypted tunnel control |
| GET | `/api/approvals/pending`, POST `/api/approvals/{id}/approve|reject` | Approval triage |
| GET | `/api/executions`, `/api/audit` | History and audit trail |
| POST | `/api/config/dry_run` | Toggle dry-run / live mode |
| POST | `/api/custom-playbooks/create` | Compile and hot-deploy typed playbooks |
