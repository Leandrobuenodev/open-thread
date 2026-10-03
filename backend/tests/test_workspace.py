import io
from uuid import uuid4

import pytest
from app.auth import AuthenticatedUser, get_current_user
from app.persistence import identity
from app.token_budget import ContextBudget
from PIL import Image
from test_chat_stream import USER, create
from test_chat_stream import live as stream_live
from test_chat_stream import setup as stream_setup

setup = stream_setup
live = stream_live


def image_bytes(kind="PNG", size=(32, 32)):
    output = io.BytesIO()
    Image.new("RGB", size, "blue").save(output, format=kind)
    return output.getvalue()


async def upload(client, cid, raw=None, media="image/png", filename="image.png"):
    return await client.post(
        f"/api/conversations/{cid}/attachments",
        params={"filename": filename},
        content=image_bytes() if raw is None else raw,
        headers={"Content-Type": media},
    )


async def send(client, cid, text="describe", ids=()):
    return await client.post(
        "/api/chat",
        json={
            "conversation_id": cid,
            "message": text,
            "stream": True,
            "attachment_ids": list(ids),
        },
    )


@pytest.mark.asyncio
async def test_image_stream_persistence_reload_and_provider(setup):
    app, client, calls, _, _ = setup
    cid = await create(client)
    response = await upload(
        client, cid, image_bytes(size=(1024, 512)), filename="../../test.png"
    )
    assert response.status_code == 201
    image = response.json()
    assert image["filename"] == "test.png"
    assert (image["width"], image["height"]) == (256, 128)
    assert "storage_reference" not in image
    result = await send(client, cid, "Describe blue", [image["id"]])
    assert result.status_code == 200 and "event: done" in result.text
    assert calls[-1]["model"] == "openthread-chat"
    parts = calls[-1]["messages"][-1]["content"]
    assert parts[0] == {"type": "text", "text": "Describe blue"}
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert ContextBudget().estimate(calls[-1]["messages"]) <= 900
    detail = (await client.get(f"/api/conversations/{cid}")).json()
    assert detail["messages"][0]["attachments"][0]["id"] == image["id"]
    assert detail["messages"][0]["attachments"][0]["size"] == image["size"]
    stored = await client.get(f"/api/conversations/{cid}/attachments/{image['id']}")
    assert (
        stored.status_code == 200
        and stored.headers["cache-control"] == "private, no-store"
    )
    assert stored.content.startswith(b"\x89PNG")
    assert (
        app.state.conversation_store.get(cid, USER)["messages"][0]["content"]
        == "Describe blue"
    )
    # Reopening/regenerating rehydrates bytes into the same provider format.
    await client.post(f"/api/conversations/{cid}/regenerate")
    assert calls[-1]["messages"][-1]["content"] == parts


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw,media,status",
    [
        (b"<svg/>", "image/svg+xml", 415),
        (b"<html/>", "image/png", 415),
        (image_bytes(), "image/jpeg", 415),
        (b"a" * (2 * 1024 * 1024 + 1), "image/png", 413),
    ],
)
async def test_invalid_uploads(setup, raw, media, status):
    _, client, _, _, _ = setup
    assert (
        await upload(client, await create(client), raw, media)
    ).status_code == status


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,media", [("JPEG", "image/jpeg"), ("WEBP", "image/webp")])
async def test_other_valid_images(setup, kind, media):
    _, client, _, _, _ = setup
    cid = await create(client)
    assert (await upload(client, cid, image_bytes(kind), media)).status_code == 201


@pytest.mark.asyncio
async def test_image_only_count_and_token_budget_rollback(setup):
    _, client, calls, _, _ = setup
    cid = await create(client)
    aid = (await upload(client, cid)).json()["id"]
    assert (await send(client, cid, "", [aid, aid])).status_code == 422
    assert (await send(client, cid, "x" * 512, [aid])).status_code == 422
    assert not calls
    assert (await send(client, cid, "", [aid])).status_code == 200
    assert calls[-1]["messages"][-1]["content"][0]["type"] == "image_url"
    assert (await client.get(f"/api/conversations/{cid}")).json()[
        "title"
    ] == "Image chat"


@pytest.mark.asyncio
async def test_upload_ownership_and_cleanup(setup):
    app, client, _, _, _ = setup
    cid = await create(client)
    aid = (await upload(client, cid)).json()["id"]
    reference = app.state.conversation_store.attachment(cid, aid, USER)[
        "storage_reference"
    ]
    assert app.state.conversation_store.storage.read(reference)
    other = await create(client)
    assert (await send(client, other, "steal", [aid])).status_code == 404
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        "other", USER.tenant_id
    )
    assert (await upload(client, cid)).status_code == 404
    assert (
        await client.get(f"/api/conversations/{cid}/attachments/{aid}")
    ).status_code == 404
    assert (
        await client.delete(f"/api/conversations/{cid}/attachments/{aid}")
    ).status_code == 404
    app.dependency_overrides[get_current_user] = lambda: USER
    assert (await client.delete(f"/api/conversations/{cid}")).status_code == 204
    from app.storage.contracts import StorageError

    with pytest.raises(StorageError):
        app.state.conversation_store.storage.read(reference)


@pytest.mark.asyncio
async def test_project_crud_pin_and_association(setup):
    _, client, _, _, _ = setup
    cid = await create(client)
    p = (await client.post("/api/projects", json={"name": " Project "})).json()
    assert p["name"] == "Project"
    assert (await client.get("/api/projects")).json()[0]["id"] == p["id"]
    assert (
        await client.patch(f"/api/projects/{p['id']}", json={"name": "Renamed"})
    ).json()["name"] == "Renamed"
    route = f"/api/conversations/{cid}"
    assert (
        await client.patch(route, json={"project_id": p["id"], "is_pinned": True})
    ).status_code == 200
    detail = (await client.get(route)).json()
    assert detail["is_pinned"] and detail["project_id"] == p["id"]
    assert (await client.get("/api/conversations")).json()[0]["is_pinned"]
    await client.patch(route, json={"project_id": None, "is_pinned": False})
    assert not (await client.get(route)).json()["is_pinned"]
    await client.patch(route, json={"project_id": p["id"], "is_pinned": True})
    assert (await client.delete(f"/api/projects/{p['id']}")).status_code == 204
    detail = (await client.get(route)).json()
    assert detail["project_id"] is None and detail["is_pinned"]
    await client.delete(route)
    assert (await client.get("/api/conversations")).json() == []


@pytest.mark.asyncio
async def test_project_pin_cross_user_and_tenant_ownership(setup):
    app, client, _, _, _ = setup
    cid = await create(client)
    pid = (await client.post("/api/projects", json={"name": "private"})).json()["id"]
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        USER.object_id, "other-tenant"
    )
    other = await create(client)
    assert (await client.get("/api/projects")).json() == []
    assert (
        await client.patch(f"/api/projects/{pid}", json={"name": "stolen"})
    ).status_code == 404
    assert (await client.delete(f"/api/projects/{pid}")).status_code == 404
    assert (
        await client.patch(f"/api/conversations/{cid}", json={"is_pinned": True})
    ).status_code == 404
    assert (
        await client.patch(f"/api/conversations/{other}", json={"project_id": pid})
    ).status_code == 404


@pytest.mark.asyncio
async def test_edit_supersedes_branch_and_regenerates_with_correct_context(setup):
    app, client, calls, _, _ = setup
    cid = await create(client)
    await send(client, cid, "original")
    await send(client, cid, "later")
    old = (await client.get(f"/api/conversations/{cid}")).json()["messages"]
    route = f"/api/conversations/{cid}/messages/{old[0]['id']}/edit"
    result = await client.post(route, json={"message": "edited"})
    assert result.status_code == 200 and "event: done" in result.text
    rows = (await client.get(f"/api/conversations/{cid}")).json()["messages"]
    assert all(m["status"] == "superseded" for m in rows[:4])
    assert rows[-2]["replaces_id"] == old[0]["id"]
    assert calls[-1]["messages"] == [{"role": "user", "content": "edited"}]
    assert [m["sequence"] for m in rows] == list(range(1, 7))
    await client.post(f"/api/conversations/{cid}/regenerate")
    assert calls[-1]["messages"] == [{"role": "user", "content": "edited"}]
    assert (await client.post(route, json={"message": "again"})).status_code == 404
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        "other", USER.tenant_id
    )
    assert (
        await client.post(
            f"/api/conversations/{cid}/messages/{rows[-2]['id']}/edit",
            json={"message": "steal"},
        )
    ).status_code == 404


@pytest.mark.asyncio
async def test_edit_image_preserved_and_upstream_failure_keeps_branch(setup):
    _, client, calls, config, _ = setup
    cid = await create(client)
    aid = (await upload(client, cid)).json()["id"]
    await send(client, cid, "original", [aid])
    original = (await client.get(f"/api/conversations/{cid}")).json()["messages"][0]
    config["status"] = 500
    result = await client.post(
        f"/api/conversations/{cid}/messages/{original['id']}/edit",
        json={"message": "edited"},
    )
    assert "event: error" in result.text
    rows = (await client.get(f"/api/conversations/{cid}")).json()["messages"]
    assert rows[0]["status"] == "superseded"
    assert rows[-2]["status"] == "failed" and rows[-2]["attachments"]
    assert rows[-1]["status"] == "failed"
    assert calls[-1]["messages"][-1]["content"][0]["text"] == "edited"
    config["status"] = 200
    assert (
        "event: done"
        in (await client.post(f"/api/conversations/{cid}/regenerate")).text
    )


@pytest.mark.asyncio
async def test_draft_replace_and_discard(setup):
    app, client, _, _, _ = setup
    cid = await create(client)
    first = (await upload(client, cid)).json()["id"]
    second = (await upload(client, cid)).json()["id"]
    assert first != second
    assert (
        await client.get(f"/api/conversations/{cid}/attachments/{first}")
    ).status_code == 404
    assert (
        await client.delete(f"/api/conversations/{cid}/attachments/{second}")
    ).status_code == 204
    assert (
        app.state.conversation_store.repository.query(identity(USER), "a:" + cid + ":")
        == []
    )


@pytest.mark.asyncio
async def test_edit_stop_reload_and_regenerate(live):
    import asyncio
    import threading

    from test_chat_stream import through_delta

    _, client, calls, config, streams = live
    cid = await create(client)
    await send(client, cid, "old")
    original = (await client.get(f"/api/conversations/{cid}")).json()["messages"][0][
        "id"
    ]
    config["gate"] = threading.Event()
    async with client.stream(
        "POST",
        f"/api/conversations/{cid}/messages/{original}/edit",
        json={"message": "edited"},
    ) as response:
        assert (await through_delta(response.aiter_lines()))["text"] == "Hello"
    for _ in range(100):
        data = (await client.get(f"/api/conversations/{cid}")).json()
        if data["messages"][-1]["status"] != "pending":
            break
        await asyncio.sleep(0.01)
    assert data["messages"][-1]["status"] == "cancelled"
    assert data["messages"][-2]["replaces_id"] == original
    assert data["messages"][0]["status"] == "superseded"
    assert streams[-1].closed.is_set()
    config["gate"] = None
    assert (
        "event: done"
        in (await client.post(f"/api/conversations/{cid}/regenerate")).text
    )
    assert calls[-1]["messages"] == [{"role": "user", "content": "edited"}]


@pytest.mark.asyncio
async def test_library_not_limited_to_recent_page_and_is_owned(setup):
    app, client, _, _, _ = setup
    store = app.state.conversation_store
    pinned = store.create(USER)["id"]
    store.metadata(pinned, USER, {"is_pinned": True})
    for _ in range(55):
        store.create(USER)
    assert not any(
        c["id"] == pinned for c in (await client.get("/api/conversations")).json()
    )
    assert [c["id"] for c in (await client.get("/api/library")).json()] == [pinned]
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        "other", USER.tenant_id
    )
    assert (await client.get("/api/library")).json() == []


@pytest.mark.asyncio
async def test_upload_chunked_limit_and_rate_admission(setup):
    from app.protection import ChatAdmission, ChatLimits

    app, client, _, _, _ = setup
    cid = await create(client)

    async def oversized():
        yield b"a" * (1024 * 1024)
        yield b"b" * (1024 * 1024 + 1)

    response = await client.post(
        f"/api/conversations/{cid}/attachments",
        content=oversized(),
        headers={"Content-Type": "image/png"},
    )
    assert response.status_code == 413
    app.state.chat_admission = ChatAdmission(ChatLimits(requests_per_window=1))
    assert (await upload(client, cid)).status_code == 201
    response = await upload(client, cid)
    assert response.status_code == 429 and response.headers.get("retry-after")


@pytest.mark.asyncio
async def test_animated_image_rejected(setup):
    _, client, _, _, _ = setup
    output = io.BytesIO()
    Image.new("RGB", (16, 16), "blue").save(
        output,
        format="WEBP",
        save_all=True,
        append_images=[Image.new("RGB", (16, 16), "red")],
        duration=100,
        loop=0,
    )
    assert (
        await upload(client, await create(client), output.getvalue(), "image/webp")
    ).status_code == 415


@pytest.mark.asyncio
async def test_edit_budget_validation_rolls_back_supersession(setup):
    _, client, calls, _, _ = setup
    cid = await create(client)
    aid = (await upload(client, cid)).json()["id"]
    await send(client, cid, "original", [aid])
    rows = (await client.get(f"/api/conversations/{cid}")).json()["messages"]
    response = await client.post(
        f"/api/conversations/{cid}/messages/{rows[0]['id']}/edit",
        json={"message": "x" * 512},
    )
    assert response.status_code == 422
    after = (await client.get(f"/api/conversations/{cid}")).json()["messages"]
    assert after == rows and len(calls) == 1


@pytest.mark.asyncio
async def test_workspace_routes_require_bearer(setup):
    app, client, _, _, _ = setup
    cid = await create(client)
    app.dependency_overrides.pop(get_current_user)
    for method, path, kwargs in [
        ("GET", "/api/projects", {}),
        ("GET", "/api/library", {}),
        ("POST", "/api/projects", {"json": {"name": "Test"}}),
        ("PATCH", f"/api/conversations/{cid}", {"json": {"is_pinned": True}}),
        (
            "POST",
            f"/api/conversations/{cid}/attachments",
            {"content": image_bytes(), "headers": {"Content-Type": "image/png"}},
        ),
        (
            "POST",
            f"/api/conversations/{cid}/messages/{uuid4()}/edit",
            {"json": {"message": "edited"}},
        ),
    ]:
        assert (await client.request(method, path, **kwargs)).status_code == 401
