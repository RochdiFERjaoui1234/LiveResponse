import pytest
import pytest_asyncio
import yaml
from httpx import AsyncClient, ASGITransport
from pathlib import Path

from soar.config import Config
from soar.state import State
from soar.audit import AuditLog
from soar.engine import PlaybookEngine
from soar.api import create_app
from soar.models import Alert

import sys
sys.path.insert(0, str(Path(__file__).parent))


@pytest_asyncio.fixture
async def app_client(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        "server:\n  port: 8088\nsecrets:\n  vt_api_key: \"envvalue\"\n",
        encoding="utf-8",
    )
    config = Config(str(cfg_path))
    config.set("engine.dry_run", True)

    state = State(tmp_path / "s.db")
    await state.init()
    audit = AuditLog(tmp_path / "a.jsonl")

    engine = PlaybookEngine(
        config=config,
        state=state,
        audit=audit,
        playbooks_dir=tmp_path / "pb",
        whitelist=["127.0.0.0/8"],
    )
    engine.load_playbooks()

    app = create_app({
        "config": config,
        "state": state,
        "audit": audit,
        "engine": engine,
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, config


@pytest.mark.asyncio
async def test_secrets_masked_and_persisted(app_client):
    client, config = app_client

    # GET masks existing values (from env-expanded config)
    masked = (await client.get("/api/secrets")).json()
    assert masked["vt_api_key"] == "****"

    # POST persists to secrets.local.yaml and wins in memory
    value = "cf-secret-token-123456789"
    res = await client.post("/api/secrets", json={"values": {"cloudflare_api_token": value}})
    assert res.status_code == 200
    assert res.json()["success"] is True

    saved = yaml.safe_load(config.secrets_path().read_text(encoding="utf-8"))
    assert saved["secrets"]["cloudflare_api_token"] == value
    assert config.get("secrets.cloudflare_api_token") == value

    masked = (await client.get("/api/secrets")).json()
    assert masked["cloudflare_api_token"].startswith("cf-s")
    assert masked["cloudflare_api_token"].endswith("789")


@pytest.mark.asyncio
async def test_secrets_reload_wins_over_env(tmp_path):
    # secrets.local.yaml written later must override env-expanded config at load
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("secrets:\n  vt_api_key: \"${VT_API_KEY}\"\n", encoding="utf-8")
    sp = tmp_path / "secrets.local.yaml"
    sp.write_text("secrets:\n  vt_api_key: \"local-override-key\"\n", encoding="utf-8")
    config = Config(str(cfg_path))
    assert config.get("secrets.vt_api_key") == "local-override-key"


@pytest.mark.asyncio
async def test_tunnel_dry_run_and_unknown_op():
    from soar.actions import tunnel
    alert = Alert(source="manual")
    dry_ctx = {"dry_run": True, "render": lambda s: s}

    res = await tunnel.execute({"operation": "up"}, alert, dry_ctx)
    assert res.success and res.simulated
    assert "warp-cli connect" in res.output

    res = await tunnel.execute({"operation": "explode"}, alert, dry_ctx)
    assert not res.success
    assert "Unknown tunnel operation" in res.error


def test_tunnel_registered():
    from soar.actions import EXECUTORS
    assert "tunnel" in EXECUTORS
