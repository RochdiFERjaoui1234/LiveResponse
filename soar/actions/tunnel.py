from __future__ import annotations
import asyncio
import shutil
import subprocess
import time
from ..models import Alert, ActionResult

OPERATIONS: dict[str, list[str]] = {
    "up": ["connect"],
    "down": ["disconnect"],
    "status": ["status"],
}

WINDOWS_WARP_CLI = r"C:\Program Files\Cloudflare\Cloudflare WARP\warp-cli.exe"


def _cli_path() -> str | None:
    found = shutil.which("warp-cli")
    if found:
        return found
    # Common Windows install location is not on PATH
    return WINDOWS_WARP_CLI if __import__("os").path.exists(WINDOWS_WARP_CLI) else None


def _run(cli: str, args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [cli] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.returncode, (proc.stdout or "").strip() or (proc.stderr or "").strip()


async def execute(params: dict, alert: Alert, ctx: dict) -> ActionResult:
    op = str(params.get("operation", "status")).lower()
    name = f"tunnel:{op}"
    started = time.time()

    args = OPERATIONS.get(op)
    if args is None:
        return ActionResult(
            action=name,
            success=False,
            error=f"Unknown tunnel operation '{op}'. Valid operations: {list(OPERATIONS.keys())}",
            duration_ms=0,
        )

    if ctx["dry_run"]:
        return ActionResult(
            action=name,
            success=True,
            simulated=True,
            output=f"[DRY-RUN SIMULATION] Would run: warp-cli {args[0]}",
            duration_ms=int((time.time() - started) * 1000),
        )

    cli = await asyncio.to_thread(_cli_path)
    if not cli:
        return ActionResult(
            action=name,
            success=False,
            error=(
                "Cloudflare WARP client not found. Install the Cloudflare WARP client "
                "(https://one.dash.cloudflare.com) so that 'warp-cli' is available."
            ),
            duration_ms=int((time.time() - started) * 1000),
        )

    try:
        code, output = await asyncio.to_thread(_run, cli, args)
        return ActionResult(
            action=name,
            success=(code == 0),
            output=output,
            error="" if code == 0 else f"warp-cli exited with status {code}",
            duration_ms=int((time.time() - started) * 1000),
        )
    except Exception as e:
        return ActionResult(
            action=name,
            success=False,
            error=f"Tunnel Operation Failed: {str(e)}",
            duration_ms=int((time.time() - started) * 1000),
        )
