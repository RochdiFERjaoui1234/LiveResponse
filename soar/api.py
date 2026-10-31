from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .models import Alert

class ApprovalDecision(BaseModel):
    resolved_by: str = "security_analyst"

class TriggerRequest(BaseModel):
    src_ip: Optional[str] = "198.51.100.45"
    target_host: Optional[str] = "web-prod-01"
    target_user: Optional[str] = "www-data"
    file_path: Optional[str] = "/var/www/html/uploads/shell.php"
    target_contract: Optional[str] = "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"
    force_dry_run: Optional[bool] = None
    custom_params: dict[str, Any] = Field(default_factory=dict)

class DryRunToggle(BaseModel):
    enabled: bool

class CreateCustomPlaybookRequest(BaseModel):
    filename: str
    code: str

class SecretsUpdate(BaseModel):
    values: dict[str, str] = Field(default_factory=dict)

from .types import PlaybookCategory
from .sdk.templates import TEMPLATES

def create_app(ctx: dict) -> FastAPI:
    static_dir = Path(__file__).parent / "static"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await ctx["state"].init()
        ctx["engine"].load_playbooks()
        print(f"[LIVE RESPONSE] Initialized successfully. Loaded {len(ctx['engine'].playbooks)} playbooks.")
        yield

    app = FastAPI(
        title="Live Response",
        version="1.0.0",
        description="Out-of-Band Security Orchestration, Automation, and Response Platform",
        lifespan=lifespan,
    )

    # Health & System Status
    @app.get("/health")
    async def health():
        return {
            "status": "healthy",
            "version": "1.0.0",
            "playbooks_loaded": len(ctx["engine"].playbooks),
            "dry_run": ctx["engine"].dry_run,
        }

    @app.get("/api/stats")
    async def get_stats():
        stats = await ctx["state"].get_stats()
        stats["dry_run"] = ctx["engine"].dry_run
        stats["playbooks_count"] = len(ctx["engine"].playbooks)
        return stats

    # Categories API (Static typing taxonomy)
    @app.get("/api/categories")
    async def get_categories():
        return [{"id": c.name, "name": c.value} for c in PlaybookCategory]

    # Starter SDK Templates
    @app.get("/api/sdk/templates")
    async def get_templates():
        return TEMPLATES

    # Custom Statically-Typed Playbook Creator
    @app.post("/api/custom-playbooks/create")
    async def create_custom_playbook(body: CreateCustomPlaybookRequest):
        try:
            spec = ctx["engine"].custom_loader.save_and_compile(body.filename, body.code)
            ctx["engine"].register_playbook(spec)
            await ctx["audit"].log("custom_playbook_deployed", {
                "playbook": spec.name,
                "category": spec.category,
                "filename": body.filename,
                "actions_count": len(spec.actions),
            })
            return {
                "success": True,
                "playbook": {
                    "name": spec.name,
                    "description": spec.description,
                    "category": spec.category,
                    "severity": spec.severity,
                    "actions_count": len(spec.actions),
                }
            }
        except Exception as e:
            raise HTTPException(400, f"Compilation / Validation Error: {str(e)}")

    # Bring-Your-Own-Key secret management (stored in config/secrets.local.yaml)
    @app.get("/api/secrets")
    async def get_secrets():
        secrets = ctx["config"].get("secrets", {}) or {}

        def mask(v: Any) -> str:
            v = str(v or "")
            if not v or v.startswith("${"):
                return ""
            return (v[:4] + "..." + v[-4:]) if len(v) > 12 else "****"
        return {k: mask(v) for k, v in secrets.items()}

    @app.post("/api/secrets")
    async def update_secrets(body: SecretsUpdate):
        try:
            merged = ctx["config"].merge_secrets(body.values)
        except Exception as e:
            raise HTTPException(500, f"Failed to persist secrets: {str(e)}")
        await ctx["audit"].log("secrets_updated", {"fields": sorted(body.values.keys())})
        return {"success": True, "fields": list(merged.keys())}

    # Encrypted Tunnel (Cloudflare WARP) status control
    @app.get("/api/tunnel/status")
    async def tunnel_status():
        from .actions import tunnel as tunnel_mod
        alert = Alert(source="manual", title="Tunnel status check")
        ctx_data = {
            "config": ctx["config"], "state": ctx["state"], "audit": ctx["audit"],
            "execution_id": "status", "dry_run": False,
            "render": lambda s: s,
        }
        res = await tunnel_mod.execute({"operation": "status"}, alert, ctx_data)
        connected = res.success and "Connected" in res.output
        return {"success": res.success, "connected": connected, "output": res.output, "error": res.error}

    @app.post("/api/tunnel/{op}")
    async def tunnel_toggle(op: str):
        if op not in ("up", "down"):
            raise HTTPException(400, "Valid tunnel operations: up, down")
        from .actions import tunnel as tunnel_mod
        alert = Alert(source="manual", title=f"Tunnel {op}")
        ctx_data = {
            "config": ctx["config"], "state": ctx["state"], "audit": ctx["audit"],
            "execution_id": f"tunnel_{op}", "dry_run": False,
            "render": lambda s: s,
        }
        res = await tunnel_mod.execute({"operation": op}, alert, ctx_data)
        await ctx["audit"].log("tunnel_operation", {"operation": op, "success": res.success, "output": res.output, "error": res.error})
        return {"success": res.success, "output": res.output, "error": res.error}

    # Playbooks & 1-Click Trigger
    @app.get("/api/playbooks")
    async def list_playbooks():
        return [
            {
                "name": p.name,
                "description": p.description,
                "category": p.category,
                "severity": p.severity,
                "ui_icon": p.ui_icon,
                "trigger": p.trigger,
                "conditions": p.conditions,
                "actions": [
                    {
                        "name": a.name,
                        "type": a.type,
                        "requires_approval": a.requires_approval,
                        "always_execute": a.always_execute,
                        "params": a.params,
                    }
                    for a in p.actions
                ],
                "rollback": [r.name for r in p.rollback],
            }
            for p in ctx["engine"].playbooks
        ]

    @app.post("/api/playbooks/{name}/trigger")
    async def trigger_playbook(name: str, body: TriggerRequest):
        target_pb = next((p for p in ctx["engine"].playbooks if p.name == name), None)
        if not target_pb:
            raise HTTPException(404, f"Playbook '{name}' not found")

        # Construct alert representation
        contract_addr = body.target_contract or body.custom_params.get("target_contract")
        alert = Alert(
            source=target_pb.trigger.get("source", "manual"),
            category=target_pb.trigger.get("category"),
            rule_id=str(target_pb.trigger.get("rule_id", "manual_trigger")),
            severity=target_pb.severity,
            title=f"Manual Simulation: {target_pb.name}",
            description=f"Triggered via Super SOAR Console for {target_pb.name}",
            src_ip=body.src_ip,
            target_host=body.target_host,
            target_user=body.target_user,
            file_path=body.file_path,
            target_contract=contract_addr,
            raw=body.custom_params,
        )

        original_dry_run = ctx["engine"].dry_run
        if body.force_dry_run is not None:
            ctx["engine"].dry_run = body.force_dry_run

        try:
            exec_result = await ctx["engine"].execute(target_pb, alert)
            return {
                "success": exec_result.status in ("success", "simulated"),
                "execution": exec_result.model_dump(mode="json"),
            }
        finally:
            ctx["engine"].dry_run = original_dry_run

    # Webhook Ingestion for Wazuh / Suricata / Custom
    @app.post("/webhook/{source}")
    async def ingest_webhook(source: str, request: Request):
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(400, "Invalid JSON payload")

        # Map common SIEM fields
        alert = Alert(
            source=source,
            rule_id=str(body.get("rule", {}).get("id", body.get("rule_id", ""))) or None,
            category=body.get("category", body.get("rule", {}).get("groups", [""])[0] if body.get("rule") else None),
            severity=str(body.get("rule", {}).get("level", body.get("severity", "medium"))),
            title=body.get("rule", {}).get("description", body.get("title", f"Alert from {source}")),
            description=body.get("full_log", body.get("description", "")),
            src_ip=body.get("data", {}).get("srcip", body.get("src_ip")),
            target_user=body.get("data", {}).get("dstuser", body.get("target_user")),
            target_host=body.get("agent", {}).get("name", body.get("target_host", "production_server")),
            file_path=body.get("data", {}).get("file", body.get("file_path")),
            target_contract=body.get("data", {}).get("contract", body.get("target_contract")),
            raw=body,
        )

        matching = ctx["engine"].matching_playbooks(alert)
        executions = []
        for pb in matching:
            has_approval = any(a.requires_approval for a in pb.actions) and not ctx["engine"].dry_run
            if has_approval:
                import asyncio
                asyncio.create_task(ctx["engine"].execute(pb, alert))
                executions.append({"playbook": pb.name, "status": "awaiting_approval"})
            else:
                res = await ctx["engine"].execute(pb, alert)
                executions.append(res.model_dump(mode="json"))

        return {
            "alert_id": alert.id,
            "matched_playbooks": len(matching),
            "executions": executions,
        }

    # Executions History
    @app.get("/api/executions")
    async def get_executions(limit: int = 50):
        return await ctx["state"].recent_executions(limit)

    # Approvals API
    @app.get("/api/approvals/pending")
    async def get_pending_approvals():
        return await ctx["state"].list_pending_approvals()

    @app.post("/api/approvals/{approval_id}/approve")
    async def approve_action(approval_id: str, body: ApprovalDecision):
        appr = await ctx["state"].get_approval(approval_id)
        if not appr:
            raise HTTPException(404, "Approval not found")
        await ctx["state"].resolve_approval(approval_id, "approved", body.resolved_by)
        await ctx["audit"].log("approval_resolved", {
            "approval_id": approval_id,
            "decision": "approved",
            "resolved_by": body.resolved_by,
        })
        return {"status": "approved", "approval_id": approval_id}

    @app.post("/api/approvals/{approval_id}/reject")
    async def reject_action(approval_id: str, body: ApprovalDecision):
        appr = await ctx["state"].get_approval(approval_id)
        if not appr:
            raise HTTPException(404, "Approval not found")
        await ctx["state"].resolve_approval(approval_id, "rejected", body.resolved_by)
        await ctx["audit"].log("approval_resolved", {
            "approval_id": approval_id,
            "decision": "rejected",
            "resolved_by": body.resolved_by,
        })
        return {"status": "rejected", "approval_id": approval_id}

    # Audit Log Inspector
    @app.get("/api/audit")
    async def get_audit_log(limit: int = 50):
        return await ctx["audit"].read_recent(limit)

    # Whitelist
    @app.get("/api/whitelist")
    async def get_whitelist():
        return {"entries": ctx["engine"].whitelist}

    # Config dry-run toggle
    @app.post("/api/config/dry_run")
    async def toggle_dry_run(body: DryRunToggle):
        ctx["engine"].dry_run = body.enabled
        return {"dry_run": ctx["engine"].dry_run}

    # Mount UI Static Assets
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", response_class=HTMLResponse)
        async def serve_index():
            index_path = static_dir / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
            return HTMLResponse("<h1>Live Response</h1><p>Static files missing.</p>")

    return app
