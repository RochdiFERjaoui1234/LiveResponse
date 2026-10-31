import pytest
import pytest_asyncio
import os
from pathlib import Path
from soar.config import Config
from soar.state import State
from soar.audit import AuditLog
from soar.engine import PlaybookEngine
from soar.models import Alert

@pytest_asyncio.fixture
async def setup_engine(tmp_path):
    state_file = tmp_path / "test_state.db"
    audit_file = tmp_path / "test_audit.jsonl"
    playbooks_dir = Path("playbooks")
    whitelist = ["127.0.0.0/8", "10.0.0.0/8", "192.168.0.0/16"]

    config = Config("config/config.yaml")
    config.set("engine.dry_run", True)
    config.set("targets.production_server.type", "ssh")
    config.set("targets.production_server.host", "127.0.0.1")

    state = State(state_file)
    await state.init()

    audit = AuditLog(audit_file)
    engine = PlaybookEngine(
        config=config,
        state=state,
        audit=audit,
        playbooks_dir=playbooks_dir,
        whitelist=whitelist,
    )
    engine.load_playbooks()
    return engine, state, audit

@pytest.mark.asyncio
async def test_playbooks_loaded(setup_engine):
    engine, _, _ = setup_engine
    assert len(engine.playbooks) >= 5
    names = [p.name for p in engine.playbooks]
    assert "php2shell_webshell_defense" in names
    assert "ddos_flood_mitigation" in names
    assert "ssh_brute_force_response" in names

@pytest.mark.asyncio
async def test_php2shell_trigger_and_dryrun_execution(setup_engine):
    engine, state, audit = setup_engine
    
    pb = next(p for p in engine.playbooks if p.name == "php2shell_webshell_defense")
    
    alert = Alert(
        source="wazuh",
        category="webshell",
        rule_id="31106",
        src_ip="198.51.100.45",
        target_host="web-node-01",
        file_path="/var/www/html/backdoor.php",
    )
    
    # Verify matching
    assert engine._conditions_ok(pb, alert) is True
    
    # Execute in dry-run mode
    result = await engine.execute(pb, alert)
    assert result.status == "simulated"
    assert len(result.actions) == len(pb.actions)
    
    # Verify action names and simulation flags
    action_names = [a.action for a in result.actions]
    assert "lock_and_quarantine_file" in action_names
    assert "kill_rogue_php_processes" in action_names
    assert "block_attacker_ip" in action_names
    for a in result.actions:
        assert a.simulated is True
        assert a.success is True

@pytest.mark.asyncio
async def test_whitelisted_ip_aborts_ssh_action(setup_engine):
    engine, _, _ = setup_engine
    
    pb = next(p for p in engine.playbooks if p.name == "php2shell_webshell_defense")
    
    # Whitelisted internal IP
    alert = Alert(
        source="wazuh",
        category="webshell",
        rule_id="31106",
        src_ip="10.0.0.5", # In whitelist!
        file_path="/var/www/html/test.php",
    )
    
    # Conditions should reject whitelisted IP
    assert engine._conditions_ok(pb, alert) is False

@pytest.mark.asyncio
async def test_ddos_dryrun_execution(setup_engine):
    engine, _, _ = setup_engine
    pb = next(p for p in engine.playbooks if p.name == "ddos_flood_mitigation")
    
    alert = Alert(
        source="suricata",
        category="dos",
        rule_id="200100",
        src_ip="203.0.113.99",
        target_host="edge-proxy-01",
    )
    
    result = await engine.execute(pb, alert)
    assert result.status == "simulated"
    assert len(result.actions) == len(pb.actions)
