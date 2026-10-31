import pytest
import pytest_asyncio
from pathlib import Path
from soar.types import (
    PlaybookCategory,
    Severity,
    ActionType,
    OnChainActionMethod,
)
from soar.sdk import TypedPlaybook, action, trigger
from soar.custom_loader import CustomPlaybookLoader
from soar.actions import web3
from soar.models import Alert
from soar.config import Config
from soar.state import State
from soar.audit import AuditLog
from soar.engine import PlaybookEngine
from soar.api import create_app
from httpx import AsyncClient, ASGITransport

def test_static_categories_and_types():
    # Verify strict taxonomy
    assert PlaybookCategory.ON_CHAIN_WEB3.value == "On-Chain & Web3 Security"
    assert PlaybookCategory.WEB_APP.value == "Web & Application Security"
    assert PlaybookCategory.NETWORK_DDOS.value == "Network & Availability"
    assert Severity.CRITICAL.value == "critical"
    assert ActionType.WEB3.value == "web3"

def test_typed_playbook_subclass_and_spec_conversion():
    class TestContractDefender(TypedPlaybook):
        name: str = "test_onchain_guardian"
        description: str = "Emergency pause on liquidity drain"
        category: PlaybookCategory = PlaybookCategory.ON_CHAIN_WEB3
        severity: Severity = Severity.CRITICAL

        @trigger(source="web3_monitor", rule_id="88001")
        def on_drain(self):
            pass

        @action(
            name="pause_contract",
            action_type=ActionType.WEB3,
            params={"target_contract": "0x1111111111111111111111111111111111111111"}
        )
        def do_pause(self):
            pass

    instance = TestContractDefender()
    spec = instance.to_spec()
    assert spec.name == "test_onchain_guardian"
    assert spec.category == "On-Chain & Web3 Security"
    assert spec.severity == "critical"
    assert len(spec.actions) == 1
    assert spec.actions[0].name == "pause_contract"
    assert spec.actions[0].type == "web3"

@pytest.mark.asyncio
async def test_onchain_web3_dryrun_execution():
    alert = Alert(
        source="web3_sentry",
        category="defi_exploit",
        raw={"target_contract": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"}
    )
    ctx = {
        "config": Config("config/config.yaml"),
        "dry_run": True,
        "render": lambda s: s,
    }
    params = {
        "network": "ethereum",
        "target_contract": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "method": "pause",
    }
    result = await web3.execute(params, alert, ctx)
    assert result.success is True
    assert result.simulated is True
    assert "0x8456cb59" in result.output
    assert "Simulated TxHash" in result.output

def test_custom_loader_loads_flashloan_guard():
    loader = CustomPlaybookLoader(custom_dir="./custom_playbooks")
    specs = loader.load_custom_playbooks()
    assert len(specs) >= 1
    names = [s.name for s in specs]
    assert "onchain_flashloan_guard" in names
    fl_spec = next(s for s in specs if s.name == "onchain_flashloan_guard")
    assert fl_spec.category == "On-Chain & Web3 Security"
    assert len(fl_spec.actions) == 3

@pytest_asyncio.fixture
async def app_client(tmp_path):
    state_file = tmp_path / "test_api_state.db"
    audit_file = tmp_path / "test_api_audit.jsonl"
    custom_dir = tmp_path / "custom_playbooks"
    custom_dir.mkdir()

    config = Config("config/config.yaml")
    config.set("engine.dry_run", True)
    config.set("engine.custom_playbooks_dir", str(custom_dir))

    state = State(state_file)
    await state.init()

    audit = AuditLog(audit_file)
    engine = PlaybookEngine(
        config=config,
        state=state,
        audit=audit,
        playbooks_dir="playbooks",
        whitelist=["127.0.0.0/8"],
    )
    engine.custom_loader = CustomPlaybookLoader(custom_dir)
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
async def test_api_categories_and_studio_compile(app_client):
    client, ctx = app_client

    # Verify categories endpoint
    cat_resp = await client.get("/api/categories")
    assert cat_resp.status_code == 200
    categories = cat_resp.json()
    cat_names = [c["name"] for c in categories]
    assert "On-Chain & Web3 Security" in cat_names

    # Test hot-deploying a custom typed playbook via API
    custom_code = '''
from soar.sdk import TypedPlaybook, action, trigger
from soar.types import PlaybookCategory, Severity, ActionType

class EmergencyRescuePlaybook(TypedPlaybook):
    name = "api_deployed_onchain_rescue"
    category = PlaybookCategory.ON_CHAIN_WEB3
    severity = Severity.HIGH

    @trigger(source="oracle_watchdog")
    def on_bad_oracle(self):
        pass

    @action(name="pause_vault", action_type=ActionType.WEB3, params={"target_contract": "0x123"})
    def pause_it(self):
        pass
'''
    deploy_resp = await client.post("/api/custom-playbooks/create", json={
        "filename": "emergency_rescue.py",
        "code": custom_code,
    })
    assert deploy_resp.status_code == 200
    data = deploy_resp.json()
    assert data["success"] is True
    assert data["playbook"]["name"] == "api_deployed_onchain_rescue"
    assert data["playbook"]["category"] == "On-Chain & Web3 Security"

    # Verify it is now immediately in the engine's playbooks list
    pb_names = [p.name for p in ctx["engine"].playbooks]
    assert "api_deployed_onchain_rescue" in pb_names
