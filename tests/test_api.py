import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from soar.config import Config
from soar.state import State
from soar.audit import AuditLog
from soar.engine import PlaybookEngine
from soar.api import create_app

@pytest_asyncio.fixture
async def app_client(tmp_path):
    state_file = tmp_path / "test_api_state.db"
    audit_file = tmp_path / "test_api_audit.jsonl"
    playbooks_dir = Path("playbooks")
    whitelist = ["127.0.0.0/8", "10.0.0.0/8"]

    config = Config("config/config.yaml")
    config.set("engine.dry_run", True)

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

    ctx = {
        "config": config,
        "state": state,
        "audit": audit,
        "engine": engine,
    }
    app = create_app(ctx)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, ctx

@pytest.mark.asyncio
async def test_health_and_stats(app_client):
    client, _ = app_client
    
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["playbooks_loaded"] >= 5

    resp = await client.get("/api/stats")
    assert resp.status_code == 200
    stats = resp.json()
    assert "total_executions" in stats
    assert stats["dry_run"] is True

@pytest.mark.asyncio
async def test_list_playbooks_api(app_client):
    client, _ = app_client
    resp = await client.get("/api/playbooks")
    assert resp.status_code == 200
    pbs = resp.json()
    assert len(pbs) >= 5
    pb_names = [p["name"] for p in pbs]
    assert "php2shell_webshell_defense" in pb_names
    assert "ddos_flood_mitigation" in pb_names

@pytest.mark.asyncio
async def test_one_click_trigger_execute(app_client):
    client, _ = app_client
    
    payload = {
        "src_ip": "198.51.100.99",
        "target_host": "test-host",
        "file_path": "/var/www/uploads/cve_exploit.php",
    }
    
    resp = await client.post("/api/playbooks/php2shell_webshell_defense/trigger", json=payload)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["success"] is True
    assert res_data["execution"]["playbook"] == "php2shell_webshell_defense"
    assert res_data["execution"]["status"] == "simulated"
    assert len(res_data["execution"]["actions"]) >= 3

@pytest.mark.asyncio
async def test_webhook_ingestion(app_client):
    client, _ = app_client
    
    wazuh_alert = {
        "rule": {
            "id": "5710",
            "level": 10,
            "description": "sshd: Multiple authentication failures",
        },
        "data": {
            "srcip": "203.0.113.19",
            "dstuser": "root",
        },
        "agent": {
            "name": "bastion-01",
        },
    }
    
    resp = await client.post("/webhook/wazuh", json=wazuh_alert)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["matched_playbooks"] == 1
    assert len(res_data["executions"]) == 1
    assert res_data["executions"][0]["playbook"] == "ssh_brute_force_response"

@pytest.mark.asyncio
async def test_dry_run_toggle(app_client):
    client, ctx = app_client
    
    resp = await client.post("/api/config/dry_run", json={"enabled": False})
    assert resp.status_code == 200
    assert resp.json()["dry_run"] is False
    assert ctx["engine"].dry_run is False

    # Toggle back to True
    resp = await client.post("/api/config/dry_run", json={"enabled": True})
    assert resp.status_code == 200
    assert resp.json()["dry_run"] is True
    assert ctx["engine"].dry_run is True

