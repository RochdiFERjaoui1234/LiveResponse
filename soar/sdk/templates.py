"""
Starter code templates with static typing for custom playbooks.
Users can copy, customize, or load these directly from the Web Studio.
"""

TYPED_PYTHON_ONCHAIN_TEMPLATE = '''"""
Custom On-Chain Web3 Threat Response Playbook.
Author: Security Engineer
Category: On-Chain & Web3 Security
"""

from soar.sdk import TypedPlaybook, action, trigger, condition
from soar.types import PlaybookCategory, Severity, ActionType, OnChainNetwork

class OnChainSecurityResponder(TypedPlaybook):
    name: str = "custom_onchain_guardian"
    description: str = "Monitors on-chain DeFi contracts and automatically invokes emergency pause upon liquidity drain."
    category: PlaybookCategory = PlaybookCategory.ON_CHAIN_WEB3
    severity: Severity = Severity.CRITICAL
    ui_icon: str = "link"

    @trigger(source="web3_monitor", category="onchain_exploit", rule_id="99001")
    def on_anomaly(self):
        """Triggered when an on-chain anomaly or high-value drain alert occurs."""
        pass

    @action(
        name="pause_exploited_contract",
        action_type=ActionType.WEB3,
        requires_approval=False,
        params={
            "network": "ethereum",
            "target_contract": "{{ alert.target_contract }}",
            "method": "pause",
            "abi_method_signature": "pause()",
        }
    )
    def trigger_pause(self):
        """Immediately calls emergency pause() on the victim smart contract."""
        pass

    @action(
        name="revoke_infinite_approvals",
        action_type=ActionType.WEB3,
        params={
            "network": "ethereum",
            "target_contract": "{{ alert.target_contract }}",
            "method": "revoke_approval",
            "abi_method_signature": "approve(address,uint256)",
        }
    )
    def revoke_allowances(self):
        """Resets token spend allowances to 0 to prevent rogue transfers."""
        pass

    @action(
        name="broadcast_multisig_alert",
        action_type=ActionType.HTTP,
        always_execute=True,
        params={
            "method": "POST",
            "url": "{{ secrets.slack_webhook }}",
            "json": {
                "text": "🛡️ *On-Chain Circuit Breaker Activated* for contract `{{ alert.target_contract }}` on Ethereum!"
            }
        }
    )
    def notify_war_room(self):
        """Dispatches real-time broadcast to multisig incident team."""
        pass
'''

TYPED_PYTHON_WEB_TEMPLATE = '''"""
Custom Server & Web Application Defense Playbook.
Author: SOC Analyst
Category: Web & Application Security
"""

from soar.sdk import TypedPlaybook, action, trigger
from soar.types import PlaybookCategory, Severity, ActionType

class CustomWebDefender(TypedPlaybook):
    name: str = "custom_web_containment"
    description: str = "Custom automated defense script against remote code execution and web backdoors."
    category: PlaybookCategory = PlaybookCategory.WEB_APP
    severity: Severity = Severity.HIGH
    ui_icon: str = "code"

    @trigger(source="waf", category="rce_attempt")
    def on_attack(self):
        pass

    @action(
        name="quarantine_target_file",
        action_type=ActionType.SSH,
        params={
            "target": "production_server",
            "command": "chmod 000 '{{ alert.file_path }}' && mv '{{ alert.file_path }}' /tmp/quarantine/",
        }
    )
    def quarantine_file(self):
        pass

    @action(
        name="drop_attacker_ip",
        action_type=ActionType.SSH,
        params={
            "target": "production_server",
            "command": "iptables -I INPUT -s {{ alert.src_ip }} -j DROP",
        }
    )
    def block_ip(self):
        pass
'''

TEMPLATES = {
    "onchain_web3": {
        "title": "On-Chain & Web3 Smart Contract Defense",
        "category": "On-Chain & Web3 Security",
        "filename": "custom_onchain_guardian.py",
        "code": TYPED_PYTHON_ONCHAIN_TEMPLATE,
    },
    "web_app": {
        "title": "Web Application & RCE Containment",
        "category": "Web & Application Security",
        "filename": "custom_web_defender.py",
        "code": TYPED_PYTHON_WEB_TEMPLATE,
    },
}
