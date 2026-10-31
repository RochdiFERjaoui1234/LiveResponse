from __future__ import annotations
import ipaddress
from pathlib import Path
from typing import Iterable

class SafetyViolation(Exception):
    """Raised when an automated action attempts to target a whitelisted entity."""
    pass

def load_whitelist(path: str | Path) -> list[str]:
    """Load whitelisted IP addresses and CIDR networks from disk."""
    p = Path(path)
    if not p.exists():
        return []
    entries = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries

def is_whitelisted_ip(ip: str | None, entries: Iterable[str]) -> bool:
    """Check if an IP string belongs to any whitelisted IP or CIDR network."""
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip.strip())
    except ValueError:
        return False

    for entry in entries:
        entry = entry.strip()
        try:
            if "/" in entry:
                net = ipaddress.ip_network(entry, strict=False)
                if addr in net:
                    return True
            else:
                if addr == ipaddress.ip_address(entry):
                    return True
        except ValueError:
            continue
    return False

def assert_not_whitelisted(ip: str | None, entries: Iterable[str]):
    """Ensure that the given IP is not whitelisted; raise SafetyViolation otherwise."""
    if ip and is_whitelisted_ip(ip, entries):
        raise SafetyViolation(f"SAFETY INTERVENTION: Target IP {ip} is explicitly whitelisted. Action aborted.")
