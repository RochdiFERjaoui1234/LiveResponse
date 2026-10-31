from __future__ import annotations
import time
import uuid
from pathlib import Path
from typing import Any
import yaml
from jinja2 import Template

from .models import Alert, PlaybookSpec, ActionSpec, ActionResult, ExecutionResult
from .actions import get_executor
from .safety import assert_not_whitelisted, is_whitelisted_ip, SafetyViolation

OPERATORS = {
    "eq": lambda a, b: str(a) == str(b),
    "ne": lambda a, b: str(a) != str(b),
    "in": lambda a, b: a in b if isinstance(b, (list, tuple, set, str)) else False,
    "not_in": lambda a, b: a not in b if isinstance(b, (list, tuple, set, str)) else True,
    "contains": lambda a, b: str(b) in str(a or ""),
    "exists": lambda a, b: a is not None and str(a).strip() != "",
    "not_exists": lambda a, b: a is None or str(a).strip() == "",
}

def _get_alert_field(alert: Alert, field: str) -> Any:
    if hasattr(alert, field):
        val = getattr(alert, field)
        if val is not None:
            return val
    return alert.raw.get(field)

from .custom_loader import CustomPlaybookLoader

class PlaybookEngine:
    def __init__(self, config, state, audit, playbooks_dir: str | Path, whitelist: list[str]):
        self.config = config
        self.state = state
        self.audit = audit
        self.playbooks_dir = Path(playbooks_dir)
        self.whitelist = whitelist
        self.custom_loader = CustomPlaybookLoader(config.get("engine.custom_playbooks_dir", "./custom_playbooks"))
        self.playbooks: list[PlaybookSpec] = []
        self.dry_run: bool = bool(config.get("engine.dry_run", False))

    def load_playbooks(self):
        self.playbooks = []
        if not self.playbooks_dir.exists():
            self.playbooks_dir.mkdir(parents=True, exist_ok=True)

        # 1. Load YAML playbooks
        for path in sorted(self.playbooks_dir.glob("*.yaml")):
            try:
                with path.open("r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f)
                if raw and isinstance(raw, dict) and "name" in raw:
                    self.playbooks.append(PlaybookSpec(**raw))
            except Exception as e:
                print(f"[ENGINE] Warning: failed to load playbook {path.name}: {e}")

        # 2. Load custom statically-typed Python playbooks
        custom_specs = self.custom_loader.load_custom_playbooks()
        for cs in custom_specs:
            # Overwrite if exists, otherwise append
            self.playbooks = [p for p in self.playbooks if p.name != cs.name]
            self.playbooks.append(cs)

    def register_playbook(self, spec: PlaybookSpec):
        """Hot-register or update a playbook in memory."""
        self.playbooks = [p for p in self.playbooks if p.name != spec.name]
        self.playbooks.append(spec)

    def _render(self, text: str, alert: Alert, execution_id: str) -> str:
        if not isinstance(text, str) or "{{" not in text:
            return text
        secrets = self.config.get("secrets", {}) or {}
        tmpl = Template(text)
        return tmpl.render(
            alert=alert.model_dump(),
            secrets=secrets,
            execution_id=execution_id,
        )

    def _trigger_matches(self, playbook: PlaybookSpec, alert: Alert) -> bool:
        t = playbook.trigger or {}
        if "source" in t and t["source"] and t["source"] != alert.source and alert.source != "manual":
            return False
        if "category" in t and t["category"] and alert.category and t["category"] != alert.category:
            return False
        if "rule_id" in t and t["rule_id"] and alert.rule_id:
            if str(t["rule_id"]) != str(alert.rule_id):
                return False
        if "severity" in t and t["severity"]:
            allowed = t["severity"] if isinstance(t["severity"], list) else [t["severity"]]
            if alert.severity not in allowed:
                return False
        return True

    def _conditions_ok(self, playbook: PlaybookSpec, alert: Alert) -> bool:
        for cond in playbook.conditions:
            field = cond.get("field", "")
            op = cond.get("operator", "eq")
            expected = cond.get("value")
            actual = _get_alert_field(alert, field)

            if op == "not_in_whitelist":
                if not actual or is_whitelisted_ip(str(actual), self.whitelist):
                    return False
                continue

            op_fn = OPERATORS.get(op)
            if not op_fn or not op_fn(actual, expected):
                return False
        return True

    def matching_playbooks(self, alert: Alert) -> list[PlaybookSpec]:
        matched = []
        for pb in self.playbooks:
            if self._trigger_matches(pb, alert) and self._conditions_ok(pb, alert):
                matched.append(pb)
        return matched

    async def _run_action(
        self,
        spec: ActionSpec,
        alert: Alert,
        exec_id: str,
        playbook_name: str,
        rollback: bool = False,
    ) -> ActionResult:
        # Mandatory safety check: Never run containment commands against whitelisted IPs
        if spec.type in ("ssh", "agent") and alert.src_ip:
            try:
                assert_not_whitelisted(alert.src_ip, self.whitelist)
            except SafetyViolation as e:
                return ActionResult(action=spec.name, success=False, error=str(e))

        ctx = {
            "config": self.config,
            "state": self.state,
            "audit": self.audit,
            "execution_id": exec_id,
            "dry_run": self.dry_run and not spec.always_execute,
            "render": lambda s: self._render(s, alert, exec_id),
        }

        # Check approval gate
        if spec.requires_approval and not rollback and not self.dry_run:
            from .actions import approval as approval_mod
            approval_params = {
                "action_name": spec.name,
                "playbook": playbook_name,
            }
            res = await approval_mod.execute(approval_params, alert, ctx)
            if not res.success:
                return res

        executor = get_executor(spec.type)
        res = await executor(spec.params, alert, ctx)
        res.action = spec.name
        return res

    async def execute(self, playbook: PlaybookSpec, alert: Alert) -> ExecutionResult:
        exec_id = str(uuid.uuid4())
        started_time = time.time()
        result = ExecutionResult(
            execution_id=exec_id,
            playbook=playbook.name,
            alert_id=alert.id,
            status="running",
        )

        await self.state.create_execution(exec_id, playbook.name, alert.id)
        await self.audit.log(
            "execution_start",
            {
                "execution_id": exec_id,
                "playbook": playbook.name,
                "alert_id": alert.id,
                "dry_run": self.dry_run,
                "src_ip": alert.src_ip,
                "target_host": alert.target_host,
            },
        )

        try:
            for spec in playbook.actions:
                # Rate limit protection
                rate_count = await self.state.bump_rate(f"action:{spec.type}")
                max_rate = int(self.config.get("engine.max_actions_per_hour", 150))
                if rate_count > max_rate:
                    raise RuntimeError(
                        f"Action rate limit exceeded for '{spec.type}' ({rate_count}/{max_rate} per hour)"
                    )

                act_res = await self._run_action(spec, alert, exec_id, playbook.name)
                result.actions.append(act_res)
                await self.state.add_action_result(exec_id, spec.name, act_res)
                await self.audit.log(
                    "action_executed",
                    {
                        "execution_id": exec_id,
                        "action": spec.name,
                        "type": spec.type,
                        "success": act_res.success,
                        "simulated": act_res.simulated,
                        "duration_ms": act_res.duration_ms,
                    },
                )

                if not act_res.success:
                    raise RuntimeError(f"Action '{spec.name}' failed: {act_res.error}")

            result.status = "simulated" if self.dry_run else "success"
            await self.state.finish_execution(exec_id, result.status)
            await self.audit.log("execution_completed", {"execution_id": exec_id, "status": result.status})
            return result

        except Exception as e:
            # Failure occurred — trigger reverse rollback
            await self.audit.log(
                "execution_failed",
                {"execution_id": exec_id, "error": str(e), "triggering_rollback": len(playbook.rollback) > 0},
            )

            for rb_spec in reversed(playbook.rollback):
                try:
                    rb_res = await self._run_action(
                        rb_spec, alert, exec_id, playbook.name, rollback=True
                    )
                    await self.state.add_action_result(exec_id, f"rollback:{rb_spec.name}", rb_res)
                except Exception as rb_err:
                    await self.audit.log(
                        "rollback_action_failed",
                        {"execution_id": exec_id, "rollback_action": rb_spec.name, "error": str(rb_err)},
                    )

            result.status = "failed"
            await self.state.finish_execution(exec_id, "failed")
            return result

    async def run(self, alert: Alert) -> list[ExecutionResult]:
        matched = self.matching_playbooks(alert)
        results = []
        for pb in matched:
            res = await self.execute(pb, alert)
            results.append(res)
        return results
