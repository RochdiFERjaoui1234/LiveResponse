from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

class Alert(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str = "manual"
    category: Optional[str] = None
    rule_id: Optional[str] = None
    severity: str = "medium"
    title: str = ""
    description: str = ""
    src_ip: Optional[str] = None
    target_user: Optional[str] = None
    target_host: Optional[str] = "production_server"
    file_path: Optional[str] = None
    target_contract: Optional[str] = None
    raw: dict[str, Any] = Field(default_factory=dict)
    received_at: datetime = Field(default_factory=_now_utc)

class ActionSpec(BaseModel):
    name: str
    type: str  # ssh, agent, http, local, approval
    params: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False
    always_execute: bool = False

class PlaybookSpec(BaseModel):
    name: str
    description: str = ""
    category: str = "General"
    severity: str = "medium"
    ui_icon: str = "shield"
    trigger: dict[str, Any] = Field(default_factory=dict)
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[ActionSpec] = Field(default_factory=list)
    rollback: list[ActionSpec] = Field(default_factory=list)

class ActionResult(BaseModel):
    action: str
    success: bool
    output: str = ""
    error: str = ""
    simulated: bool = False
    duration_ms: int = 0

class ExecutionResult(BaseModel):
    execution_id: str
    playbook: str
    alert_id: str
    status: str  # success | failed | simulated | awaiting_approval | running
    actions: list[ActionResult] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=_now_utc)
    finished_at: Optional[datetime] = None

class ApprovalRecord(BaseModel):
    id: str
    execution_id: str
    playbook: str
    action_name: str
    alert_id: str
    status: str  # pending | approved | rejected | timeout
    created_at: float
    resolved_at: Optional[float] = None
    resolved_by: Optional[str] = None
