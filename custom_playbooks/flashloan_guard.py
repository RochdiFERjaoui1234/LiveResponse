"""
FlashLoan Guard — Statically-Typed On-Chain DeFi Security Playbook.
Demonstrates custom playbook authoring with Python type annotations and Enums.
"""

from soar.sdk import TypedPlaybook, action, trigger
from soar.types import PlaybookCategory, Severity, ActionType

class FlashLoanGuardPlaybook(TypedPlaybook):
    name: str = "onchain_flashloan_guard"
    description: str = "Statically-typed Python playbook monitoring liquidity pools for unauthorized flashloan drains."
    category: PlaybookCategory = PlaybookCategory.ON_CHAIN_WEB3
    severity: Severity = Severity.CRITICAL
    ui_icon: str = "link"

    @trigger(source="web3_sentry", category="defi_exploit", rule_id="88002")
    def on_drain_detected(self):
        """Fires when flashloan volume exceeds normal pool limits."""
        pass

    @action(
        name="pause_liquidity_pool",
        action_type=ActionType.WEB3,
        requires_approval=False,
        params={
            "network": "ethereum",
            "target_contract": "{{ alert.target_contract }}",
            "method": "pause",
            "abi_method_signature": "pause()",
        }
    )
    def pause_contract(self):
        """Calls emergency pause() on the victim smart contract."""
        pass

    @action(
        name="revoke_router_allowance",
        action_type=ActionType.WEB3,
        params={
            "network": "ethereum",
            "target_contract": "{{ alert.target_contract }}",
            "method": "revoke_approval",
            "abi_method_signature": "approve(address,uint256)",
        }
    )
    def revoke_allowance(self):
        """Zeroes out token approvals to block malicious drain routes."""
        pass

    @action(
        name="notify_security_war_room",
        action_type=ActionType.HTTP,
        always_execute=True,
        params={
            "method": "POST",
            "url": "{{ secrets.slack_webhook }}",
            "json": {
                "text": "🚨 *FLASHLOAN GUARD TRIGGERED*: Contract `{{ alert.target_contract }}` emergency paused on-chain!"
            }
        }
    )
    def alert_team(self):
        """Notifies multisig guardians and incident response team."""
        pass
