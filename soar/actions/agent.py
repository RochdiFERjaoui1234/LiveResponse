from __future__ import annotations
import hmac
import hashlib
import json
import os
import time
import uuid
import httpx
from ..models import Alert, ActionResult

async def execute(params: dict, alert: Alert, ctx: dict) -> ActionResult:
    target_name = params.get("target", "production_agent")
    target = ctx["config"].get(f"targets.{target_name}")
    command = ctx["render"](params.get("command", ""))
    started = time.time()

    if not target or target.get("type") != "agent":
        return ActionResult(
            action=f"agent:{target_name}",
            success=False,
            error=f"Target '{target_name}' not configured or not type 'agent'",
            duration_ms=0,
        )

    url = target.get("url", "http://127.0.0.1:8099/exec")
    key_env = target.get("hmac_key_env", "SOAR_AGENT_KEY")
    secret_key = os.environ.get(key_env, "").encode("utf-8")

    if ctx["dry_run"]:
        return ActionResult(
            action=f"agent:{target_name}",
            success=True,
            simulated=True,
            output=f"[DRY-RUN SIMULATION] Would dispatch to Go Agent ({url}):\n$ {command}",
            duration_ms=int((time.time() - started) * 1000),
        )

    payload = {
        "id": str(uuid.uuid4()),
        "cmd": command,
        "timeout": int(params.get("timeout", 30)),
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    signature = hmac.new(secret_key, body_bytes, hashlib.sha256).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Soar-Signature": signature,
    }

    try:
        async with httpx.AsyncClient(timeout=35) as client:
            resp = await client.post(url, content=body_bytes, headers=headers)
            if resp.status_code != 200:
                return ActionResult(
                    action=f"agent:{target_name}",
                    success=False,
                    error=f"Agent returned HTTP {resp.status_code}: {resp.text}",
                    duration_ms=int((time.time() - started) * 1000),
                )
            data = resp.json()
            err_msg = data.get("error", "")
            return ActionResult(
                action=f"agent:{target_name}",
                success=(err_msg == ""),
                output=data.get("output", "").strip(),
                error=err_msg,
                duration_ms=int((time.time() - started) * 1000),
            )
    except Exception as e:
        return ActionResult(
            action=f"agent:{target_name}",
            success=False,
            error=f"Agent Dispatch Failed: {str(e)}",
            duration_ms=int((time.time() - started) * 1000),
        )
