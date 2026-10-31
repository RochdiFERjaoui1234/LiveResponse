from __future__ import annotations
import time
import httpx
from ..models import Alert, ActionResult

async def execute(params: dict, alert: Alert, ctx: dict) -> ActionResult:
    method = params.get("method", "GET").upper()
    raw_url = params.get("url", "")
    url = ctx["render"](raw_url)
    headers = {k: ctx["render"](str(v)) for k, v in params.get("headers", {}).items()}
    body = params.get("json")
    if body and isinstance(body, dict):
        def _render_dict(d: dict) -> dict:
            out = {}
            for k, v in d.items():
                if isinstance(v, str):
                    out[k] = ctx["render"](v)
                elif isinstance(v, dict):
                    out[k] = _render_dict(v)
                else:
                    out[k] = v
            return out
        body = _render_dict(body)

    started = time.time()

    # If the URL is empty or unresolved env var, and action is not critical, skip gracefully
    if not url or url.startswith("${"):
        return ActionResult(
            action=f"http:{method}",
            success=True,
            simulated=True,
            output="[SKIPPED] HTTP URL not configured or variable unresolved",
            duration_ms=0,
        )

    # If any header contains unresolved env var (e.g. ${VT_API_KEY}) or empty API key, skip gracefully
    unresolved_auth = any(
        isinstance(v, str) and (v.startswith("${") or v.strip() == "")
        for k, v in headers.items()
        if "key" in k.lower() or "token" in k.lower() or "auth" in k.lower()
    )
    if unresolved_auth:
        return ActionResult(
            action=f"http:{method}",
            success=True,
            simulated=True,
            output=f"[SKIPPED] HTTP action skipped because API key/token is unconfigured: {url}",
            duration_ms=0,
        )

    if ctx["dry_run"] and not params.get("always_execute", False):
        return ActionResult(
            action=f"http:{method}",
            success=True,
            simulated=True,
            output=f"[DRY-RUN SIMULATION] {method} {url}\nPayload: {body}",
            duration_ms=int((time.time() - started) * 1000),
        )

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.request(method, url, headers=headers, json=body)
            success = r.status_code < 400
            return ActionResult(
                action=f"http:{method}",
                success=success,
                output=r.text[:2000],
                error="" if success else f"HTTP {r.status_code}: {r.text[:500]}",
                duration_ms=int((time.time() - started) * 1000),
            )
    except Exception as e:
        return ActionResult(
            action=f"http:{method}",
            success=False,
            error=f"HTTP Request Failed: {str(e)}",
            duration_ms=int((time.time() - started) * 1000),
        )
