from __future__ import annotations
from typing import Callable, Coroutine, Any
from . import ssh, agent, http, local, approval, web3, tunnel

EXECUTORS: dict[str, Callable[..., Coroutine[Any, Any, Any]]] = {
    "ssh": ssh.execute,
    "agent": agent.execute,
    "http": http.execute,
    "local": local.execute,
    "web3": web3.execute,
    "approval": approval.execute,
    "tunnel": tunnel.execute,
}

def get_executor(action_type: str):
    fn = EXECUTORS.get(action_type)
    if fn is None:
        raise ValueError(f"Unknown SOAR action type: '{action_type}'. Valid types: {list(EXECUTORS.keys())}")
    return fn
