from __future__ import annotations
import asyncio
import time
from ..models import Alert, ActionResult

async def execute(params: dict, alert: Alert, ctx: dict) -> ActionResult:
    command = ctx["render"](params.get("command", ""))
    started = time.time()

    if ctx["dry_run"] and not params.get("always_execute", False):
        return ActionResult(
            action="local",
            success=True,
            simulated=True,
            output=f"[DRY-RUN SIMULATION] Local command: {command}",
            duration_ms=int((time.time() - started) * 1000),
        )

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        success = (proc.returncode == 0)
        return ActionResult(
            action="local",
            success=success,
            output=stdout.decode("utf-8", errors="replace").strip(),
            error=stderr.decode("utf-8", errors="replace").strip() if not success else "",
            duration_ms=int((time.time() - started) * 1000),
        )
    except Exception as e:
        return ActionResult(
            action="local",
            success=False,
            error=f"Local Execution Failed: {str(e)}",
            duration_ms=int((time.time() - started) * 1000),
        )
