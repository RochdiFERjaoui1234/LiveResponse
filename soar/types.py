from __future__ import annotations
from enum import Enum
from typing import Any, Optional, Union
from pydantic import BaseModel, Field

class PlaybookCategory(str, Enum):
    """
    Strict static typing categories for Super SOAR playbooks.
    Ensures every playbook is properly categorized across cybersecurity domains.
    """
    ON_CHAIN_WEB3 = "On-Chain & Web3 Security"
    WEB_APP = "Web & Application Security"
    NETWORK_DDOS = "Network & Availability"
    IDENTITY_ACCESS = "Access & Authentication"
    ENDPOINT_MALWARE = "Endpoint & Ransomware"
    CLOUD_INFRA = "Cloud Infrastructure"
    GENERAL = "General Security Operations"

class Severity(str, Enum):
    """Normalized incident severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ActionType(str, Enum):
    """Supported containment execution action types."""
    SSH = "ssh"
    AGENT = "agent"
    HTTP = "http"
    LOCAL = "local"
    WEB3 = "web3"
    APPROVAL = "approval"
    TUNNEL = "tunnel"

class OnChainNetwork(str, Enum):
    """Supported EVM blockchain networks for on-chain incident response."""
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    BINANCE_SMART_CHAIN = "bsc"
    LOCAL_DEV = "local"

class OnChainActionMethod(str, Enum):
    """Common emergency response methods for smart contracts."""
    PAUSE = "pause"
    UNPAUSE = "unpause"
    REVOKE_APPROVAL = "revoke_approval"
    BLACKLIST_ADDRESS = "blacklist_address"
    TRANSFER_RESCUE = "transfer_rescue"
    QUERY_STATE = "query_state"
    CUSTOM_CALL = "custom_call"

class OnChainActionParams(BaseModel):
    """Typed parameters for on-chain containment actions."""
    network: OnChainNetwork = OnChainNetwork.ETHEREUM
    rpc_url: Optional[str] = None
    target_contract: str
    method: OnChainActionMethod = OnChainActionMethod.PAUSE
    caller_address: Optional[str] = None
    abi_method_signature: Optional[str] = "pause()"
    call_args: list[Any] = Field(default_factory=list)
    gas_limit: int = 150000

class TypedTriggerSpec(BaseModel):
    """Typed trigger definition for playbooks."""
    source: str
    category: Optional[str] = None
    rule_id: Optional[str] = None
    event_name: Optional[str] = None
    severity: Optional[list[Severity]] = None

class TypedActionSpec(BaseModel):
    """Typed action specification."""
    name: str
    type: ActionType
    params: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False
    always_execute: bool = False
