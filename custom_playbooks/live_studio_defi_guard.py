
from soar.sdk import TypedPlaybook, action, trigger
from soar.types import PlaybookCategory, Severity, ActionType

class LiveStudioDeFiGuard(TypedPlaybook):
    name: str = "studio_deployed_defi_guard"
    description: str = "Dynamically compiled on-chain guardian via Playbook Studio"
    category: PlaybookCategory = PlaybookCategory.ON_CHAIN_WEB3
    severity: Severity = Severity.CRITICAL
    ui_icon: str = "link"

    @trigger(source="onchain_watchdog", rule_id="77001")
    def on_drain(self):
        pass

    @action(
        name="emergency_pause",
        action_type=ActionType.WEB3,
        params={
            "network": "ethereum",
            "target_contract": "{{ alert.target_contract }}",
            "method": "pause",
            "abi_method_signature": "pause()",
        }
    )
    def call_pause(self):
        pass
