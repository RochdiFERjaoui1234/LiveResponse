from __future__ import annotations
import asyncio
import time
import uuid
from ..models import Alert, ActionResult
from ..notifications import notify_approval_needed

class ApprovalRejected(Exception):
    pass

class ApprovalTimeout(Exception):
    pass

async def execute(params: dict, alert: Alert, ctx: dict) -> ActionResult:
    state = ctx["state"]
    audit = ctx["audit"]
    config = ctx["config"]
    exec_id = ctx["execution_id"]
    playbook_name = params.get("playbook", "Unknown Playbook")
    action_name = params.get("action_name", "Unknown Action")
    approval_id = str(uuid.uuid4())
    started = time.time()

    if ctx["dry_run"]:
        return ActionResult(
            action=f"approval:{action_name}",
            success=True,
            simulated=True,
            output=f"[DRY-RUN SIMULATION] Approval required for '{action_name}'. Auto-simulated approval granted.",
            duration_ms=int((time.time() - started) * 1000),
        )

    # Persist pending approval in DB
    await state.create_approval(
        approval_id=approval_id,
        exec_id=exec_id,
        playbook=playbook_name,
        action=action_name,
        alert_id=alert.id,
    )

    await audit.log(
        "approval_requested",
        {
            "approval_id": approval_id,
            "execution_id": exec_id,
            "playbook": playbook_name,
            "action": action_name,
            "alert_id": alert.id,
            "src_ip": alert.src_ip,
        },
    )

    # Broadcast notification to Slack
    slack_url = config.get("secrets.slack_webhook") or ""
    if slack_url and not slack_url.startswith("${"):
        summary = f"Alert: {alert.title or alert.rule_id} | Target: {alert.target_host} | IP: {alert.src_ip}"
        await notify_approval_needed(slack_url, approval_id, playbook_name, action_name, summary)

    # Poll until resolved or timeout
    timeout_sec = int(config.get("engine.approval_timeout_seconds", 900))
    deadline = time.time() + timeout_sec

    while time.time() < deadline:
        rec = await state.get_approval(approval_id)
        if rec:
            status = rec.get("status")
            if status == "approved":
                return ActionResult(
                    action=f"approval:{action_name}",
                    success=True,
                    output=f"Approval GRANTED by {rec.get('resolved_by', 'operator')} ({approval_id})",
                    duration_ms=int((time.time() - started) * 1000),
                )
            if status == "rejected":
                return ActionResult(
                    action=f"approval:{action_name}",
                    success=False,
                    error=f"Approval REJECTED by {rec.get('resolved_by', 'operator')} ({approval_id})",
                    duration_ms=int((time.time() - started) * 1000),
                )
        await asyncio.sleep(2)

    # Timeout reached
    await state.resolve_approval(approval_id, "timeout", "system_timeout")
    return ActionResult(
        action=f"approval:{action_name}",
        success=False,
        error=f"Approval TIMEOUT after {timeout_sec}s ({approval_id})",
        duration_ms=int((time.time() - started) * 1000),
    )
