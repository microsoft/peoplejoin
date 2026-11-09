import asyncio
import stat
from types import SimpleNamespace

import jsons
import pytest
from quart.testing import WebsocketResponseError

from async_collab.agent import base_agent
from async_collab.api import App
from async_collab.core.bot import Bot
from async_collab.core.message import ChatMessage
from async_collab.core.person import Person
from async_collab.orchestrator.datum import AsyncCollabOutputDatum


@pytest.fixture
def people():
    owner = Person(person_id="alice", full_name="Alice", email="alice@example.com")
    other = Person(person_id="bob", full_name="Bob", email="bob@example.com")
    return owner, other


@pytest.fixture
def secured_app(monkeypatch, tmp_path, people):
    owner, other = people
    monkeypatch.setenv("PEOPLEJOIN_API_TOKEN", "test-private-token")
    monkeypatch.setenv("PEOPLEJOIN_EXPORT_ROOT", str(tmp_path / "exports"))
    app = App()
    app.metadata = {"tenant_id": "test", "description": "test"}
    app.agent = SimpleNamespace(
        tenant=SimpleNamespace(
            get_person_by_id=lambda person_id: {
                owner.person_id: owner,
                other.person_id: other,
            }.get(person_id)
        ),
        compile_into_datum=lambda datum_id, metadata: AsyncCollabOutputDatum(
            datum_id=datum_id,
            primary=owner,
            metadata=metadata,
            initial_message=None,
            repl_and_messages=["private transcript"],
        ),
    )
    return app.app, tmp_path / "exports"


@pytest.mark.asyncio
async def test_export_requires_operator_token(secured_app, monkeypatch):
    app, root = secured_app
    client = app.test_client()
    payload = {"folder_path": str(root), "datum_id": "session"}
    assert (await client.post("/save", json=payload)).status_code == 401
    assert (await client.get("/clear")).status_code == 401
    assert (await client.post("/init", json={})).status_code == 401
    with pytest.raises(WebsocketResponseError) as exc:
        async with client.websocket("/ws/alice"):
            pass
    assert exc.value.response.status_code == 401
    assert not root.exists()
    monkeypatch.delenv("PEOPLEJOIN_API_TOKEN")
    assert (await client.post("/save", json=payload)).status_code == 503


@pytest.mark.asyncio
async def test_export_containment_and_no_overwrite(secured_app, tmp_path):
    app, root = secured_app
    client = app.test_client()
    headers = {"Authorization": "Bearer test-private-token"}
    outside = tmp_path / "outside"
    for folder, datum_id in (
        (str(outside), "safe"),
        (str(root), "../escape"),
        (str(root), "nested/name"),
    ):
        response = await client.post(
            "/save", json={"folder_path": folder, "datum_id": datum_id}, headers=headers
        )
        assert response.status_code == 400
    root.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    response = await client.post(
        "/save",
        json={"folder_path": str(root / "link"), "datum_id": "safe"},
        headers=headers,
    )
    assert response.status_code == 400
    assert not outside.exists()
    payload = {"folder_path": str(root / "run"), "datum_id": "safe"}
    assert (
        await client.post("/save", json=payload, headers=headers)
    ).status_code == 200
    assert (root / "run/safe.datum.json").exists()
    assert (root / "run/safe.conversation.txt").read_text() == "private transcript"
    assert stat.S_IMODE((root / "run/safe.datum.json").stat().st_mode) == 0o600
    assert stat.S_IMODE((root / "run/safe.conversation.txt").stat().st_mode) == 0o600
    assert (
        await client.post("/save", json=payload, headers=headers)
    ).status_code == 409


@pytest.mark.asyncio
async def test_sender_must_match_authenticated_participant(monkeypatch, people):
    owner, other = people
    agent = base_agent.Agent.__new__(base_agent.Agent)
    agent.bot = Bot(owner=owner)
    agent.tenant = SimpleNamespace(
        get_person_by_id=lambda person_id: {
            owner.person_id: owner,
            other.person_id: other,
        }.get(person_id)
    )
    agent.agent_logger = SimpleNamespace(
        register_event=lambda message: pytest.fail("invalid message logged")
    )
    agent.on_message_received = lambda message: pytest.fail("invalid message processed")
    frame = jsons.dumps(
        ChatMessage(sender=other, recipient=agent.bot, content="forged")
    )
    monkeypatch.setattr(
        base_agent,
        "websocket",
        SimpleNamespace(receive=lambda: asyncio.sleep(0, result=frame)),
    )
    with pytest.raises(ValueError, match="sender does not match"):
        await agent.receiving(owner)


@pytest.mark.asyncio
async def test_invalid_websocket_frame_is_rejected(monkeypatch, people):
    owner, _ = people
    agent = base_agent.Agent.__new__(base_agent.Agent)
    monkeypatch.setattr(
        base_agent,
        "websocket",
        SimpleNamespace(receive=lambda: asyncio.sleep(0, result="not JSON")),
    )
    with pytest.raises(ValueError, match="Invalid websocket message"):
        await agent.receiving(owner)


@pytest.mark.asyncio
async def test_sender_metadata_must_match_tenant(monkeypatch, people):
    owner, _ = people
    agent = base_agent.Agent.__new__(base_agent.Agent)
    agent.bot = Bot(owner=owner)
    agent.tenant = SimpleNamespace(get_person_by_id=lambda person_id: owner)
    forged = Person(person_id=owner.person_id, full_name="Impostor", email=owner.email)
    frame = jsons.dumps(
        ChatMessage(sender=forged, recipient=agent.bot, content="forged")
    )
    monkeypatch.setattr(
        base_agent,
        "websocket",
        SimpleNamespace(receive=lambda: asyncio.sleep(0, result=frame)),
    )
    with pytest.raises(ValueError, match="sender does not match"):
        await agent.receiving(owner)


@pytest.mark.asyncio
async def test_outbound_messages_only_reach_recipient(monkeypatch, people):
    owner, other = people
    agent = base_agent.Agent.__new__(base_agent.Agent)
    agent.send_queue = [
        ChatMessage(sender=Bot(owner=owner), recipient=other, content="private"),
        ChatMessage(sender=Bot(owner=owner), recipient=owner, content="owner"),
    ]
    sent = []

    async def send(message):
        sent.append(jsons.loads(message)["content"])

    async def stop(_):
        raise asyncio.CancelledError

    agent.agent_logger = SimpleNamespace(register_send_message=lambda message: None)
    monkeypatch.setattr(base_agent, "websocket", SimpleNamespace(send=send))
    monkeypatch.setattr(base_agent.asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        await agent.sending(owner)
    assert sent == ["owner"]
    assert len(agent.send_queue) == 1
    assert agent.send_queue[0].recipient == other
