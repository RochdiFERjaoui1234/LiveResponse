from __future__ import annotations
import inspect
from typing import Any, Callable, Optional
from ..types import PlaybookCategory, Severity, ActionType, TypedTriggerSpec, TypedActionSpec
from ..models import PlaybookSpec, ActionSpec, Alert

def trigger(
    source: str = "custom",
    category: Optional[str] = None,
    rule_id: Optional[str] = None,
    event_name: Optional[str] = None,
    severity: Optional[list[Severity]] = None,
):
    """Decorator to bind trigger conditions to a typed playbook."""
    def decorator(fn: Callable):
        fn.__soar_trigger__ = {
            "source": source,
            "category": category,
            "rule_id": rule_id,
            "event_name": event_name,
            "severity": [s.value for s in severity] if severity else None,
        }
        return fn
    return decorator

def action(
    name: str,
    action_type: ActionType = ActionType.LOCAL,
    requires_approval: bool = False,
    always_execute: bool = False,
    params: Optional[dict[str, Any]] = None,
):
    """Decorator to mark a method as a SOAR containment action step."""
    def decorator(fn: Callable):
        fn.__soar_action__ = {
            "name": name,
            "type": action_type.value if hasattr(action_type, "value") else str(action_type),
            "requires_approval": requires_approval,
            "always_execute": always_execute,
            "params": params or {},
        }
        return fn
    return decorator

def condition(field: str, operator: str, value: Any = None):
    """Decorator to add declarative condition validation."""
    def decorator(cls_or_fn: Any):
        if not hasattr(cls_or_fn, "__soar_conditions__"):
            cls_or_fn.__soar_conditions__ = []
        cls_or_fn.__soar_conditions__.append({
            "field": field,
            "operator": operator,
            "value": value,
        })
        return cls_or_fn
    return decorator

class TypedPlaybook:
    """
    Base class for statically-typed Python Playbooks.
    Users subclass this to create type-safe custom playbooks with IDE autocompletion.
    """
    name: str = "custom_typed_playbook"
    description: str = "Custom user-authored typed playbook"
    category: PlaybookCategory = PlaybookCategory.GENERAL
    severity: Severity = Severity.MEDIUM
    ui_icon: str = "code"

    def __init__(self):
        # Validate that category is a valid PlaybookCategory enum
        if not isinstance(self.category, (PlaybookCategory, str)):
            raise TypeError(f"Playbook {self.name} category must be an instance of PlaybookCategory Enum")

    def to_spec(self) -> PlaybookSpec:
        """Converts the typed Python class into an engine-compatible PlaybookSpec."""
        actions: list[ActionSpec] = []
        trigger_dict: dict[str, Any] = {}
        conditions_list: list[dict[str, Any]] = getattr(self.__class__, "__soar_conditions__", [])

        # Inspect class attributes and decorated methods
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if callable(attr):
                if hasattr(attr, "__soar_trigger__"):
                    trigger_dict = attr.__soar_trigger__
                if hasattr(attr, "__soar_action__"):
                    act_meta = attr.__soar_action__
                    actions.append(
                        ActionSpec(
                            name=act_meta["name"],
                            type=act_meta["type"],
                            params=act_meta["params"],
                            requires_approval=act_meta["requires_approval"],
                            always_execute=act_meta["always_execute"],
                        )
                    )

        # Fallback trigger if not decorated
        if not trigger_dict:
            trigger_dict = {"source": "manual", "category": self.category.value if hasattr(self.category, "value") else str(self.category)}

        return PlaybookSpec(
            name=self.name,
            description=self.description,
            category=self.category.value if hasattr(self.category, "value") else str(self.category),
            severity=self.severity.value if hasattr(self.severity, "value") else str(self.severity),
            ui_icon=self.ui_icon,
            trigger=trigger_dict,
            conditions=conditions_list,
            actions=actions,
            rollback=[],
        )
