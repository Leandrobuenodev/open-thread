"""Table/Blob consistency and failure contracts against real loopback Azurite."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from app.auth import AuthenticatedUser
from app.persistence import ConversationStore, identity, now
from app.storage.azure import configured_storage
from app.storage.contracts import StorageConflict, StorageError
from fastapi import HTTPException

USER = AuthenticatedUser("table-user", "table-tenant")


@pytest.fixture
def store(storage_config):
    repo, blobs, _credential = configured_storage()
    yield ConversationStore(repo, blobs)
    repo.close()
    blobs.close()


def test_restart_persistence_and_no_owner_input(store):
    cid = store.create(USER)["id"]
    attempt, *_ = store.start_stream(cid, USER, "remember blue")
    store.end_stream(cid, USER, attempt, "blue", "completed")
    repo, blobs, _ = configured_storage()
    restarted = ConversationStore(repo, blobs)
    try:
        assert restarted.get(cid, USER) == store.get(cid, USER)
    finally:
        repo.close()
        blobs.close()
    with pytest.raises(HTTPException) as error:
        store.get(cid, AuthenticatedUser(USER.object_id, "other-tenant"))
    assert error.value.status_code == 404


def test_stale_etag_rejected_and_batch_rolls_back(store):
    cid = store.create(USER)["id"]
    stale = store.owned(cid, USER)
    new = dict(stale)
    new["title"] = "new"
    store.repository.batch([("update", new)])
    extra = store.record(identity(USER), "p:" + str(uuid4()), id="extra", name="Extra")
    with pytest.raises(StorageConflict):
        store.repository.batch([("create", extra), ("update", stale)])
    assert store.repository.get(identity(USER), extra["RowKey"]) is None
    assert store.get(cid, USER)["title"] == "new"


def test_two_replicas_cannot_claim_same_conversation(store):
    cid = store.create(USER)["id"]
    ready = Barrier(2)

    def claim():
        ready.wait(timeout=5)
        try:
            store.start_stream(cid, USER, "race")
            return 200
        except (HTTPException, StorageConflict):
            return 409

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: claim(), range(2))) == [200, 409]


def test_expired_lease_recovers_and_rejects_late_completion(store):
    cid = store.create(USER)["id"]
    old, *_ = store.start_stream(cid, USER, "old")
    c = store.owned(cid, USER)
    c["pending_at"] = (now() - timedelta(seconds=121)).isoformat()
    store.repository.batch([("update", c)])
    new, context, *_ = store.start_stream(cid, USER, "new")
    assert context == [{"role": "user", "content": "new"}]
    with pytest.raises(HTTPException):
        store.end_stream(cid, USER, old, "too late", "completed")
    store.end_stream(cid, USER, new, "done", "completed")
    assert [m["status"] for m in store.get(cid, USER)["messages"]] == [
        "failed",
        "failed",
        "completed",
        "completed",
    ]


def test_atomic_terminal_failure_keeps_prior_regenerated_answer(store, monkeypatch):
    cid = store.create(USER)["id"]
    a, *_ = store.start_stream(cid, USER, "prompt")
    store.end_stream(cid, USER, a, "original", "completed")
    b, *_ = store.start_stream(cid, USER)
    commit = store.repository.batch

    def failed(operations):
        raise StorageError("private transport failure")

    monkeypatch.setattr(store.repository, "batch", failed)
    with pytest.raises(StorageError):
        store.end_stream(cid, USER, b, "new", "completed")
    monkeypatch.setattr(store.repository, "batch", commit)
    assert store.get(cid, USER)["messages"][1]["status"] == "completed"
    store.end_stream(cid, USER, b, "partial", "failed")
    assert store.get(cid, USER)["messages"][1]["status"] == "completed"


def test_large_unicode_response_is_chunked_and_restored(store):
    cid = store.create(USER)["id"]
    a, *_ = store.start_stream(cid, USER, "hello")
    answer = "💙" * 16000
    store.end_stream(cid, USER, a, answer, "completed")
    assert store.get(cid, USER)["messages"][-1]["content"] == answer
    assert len(store.repository.query(identity(USER), "t:" + cid + ":")) == 2
    store.delete(cid, USER)
    assert store.repository.query(identity(USER), "t:" + cid + ":") == []


def test_edit_over_batch_limit_uses_version_marker(store):
    cid = store.create(USER)["id"]
    c = store.owned(cid, USER)
    original = None
    for start in (1, 81):
        operations = []
        for seq in range(start, start + 80):
            mid = str(uuid4())
            original = original or mid
            operations.append(
                (
                    "create",
                    store.record(
                        identity(USER),
                        f"m:{cid}:{seq:020d}:{mid}",
                        id=mid,
                        role="user" if seq % 2 else "assistant",
                        sequence=seq,
                        status="completed",
                        content="old",
                        created_at=now().isoformat(),
                    ),
                )
            )
        store.repository.batch(operations)
    c["next_sequence"] = 161
    store.repository.batch([("update", c)])
    a, context, *_ = store.start_stream(cid, USER, "edited", edit_id=original)
    store.end_stream(cid, USER, a, "answer", "completed")
    assert context == [{"role": "user", "content": "edited"}]
    detail = store.get(cid, USER)
    assert all(m["status"] == "superseded" for m in detail["messages"][:-2])
    assert len(store.repository.query(identity(USER), "v:" + cid + ":")) == 1


def test_delete_partial_blob_failure_keeps_retryable_tombstone(store, monkeypatch):
    from test_workspace import image_bytes

    cid = store.create(USER)["id"]
    store.upload(cid, USER, image_bytes(), "image/png", "a.png")
    original = store.storage.remove_prefix
    monkeypatch.setattr(
        store.storage,
        "remove_prefix",
        lambda _: (_ for _ in ()).throw(StorageError("failed")),
    )
    with pytest.raises(StorageError):
        store.delete(cid, USER)
    assert store.owned(cid, USER, True)["deleting"]
    with pytest.raises(HTTPException):
        store.get(cid, USER)
    assert store.repository.query(identity(USER), "a:" + cid + ":")
    monkeypatch.setattr(store.storage, "remove_prefix", original)
    store.delete(cid, USER)
    assert store.repository.get(identity(USER), "c:" + cid) is None
    assert store.repository.query(identity(USER), "a:" + cid + ":") == []


def test_delete_partial_entity_failure_resumes_on_list(store, monkeypatch):
    cid = store.create(USER)["id"]
    a, *_ = store.start_stream(cid, USER, "prompt")
    store.end_stream(cid, USER, a, "done", "completed")
    commit = store.repository.batch

    def fail_cleanup(operations):
        if any(
            action == "delete" and entity["RowKey"].startswith("m:")
            for action, entity in operations
        ):
            raise StorageError("failed")
        commit(operations)

    monkeypatch.setattr(store.repository, "batch", fail_cleanup)
    with pytest.raises(StorageError):
        store.delete(cid, USER)
    monkeypatch.setattr(store.repository, "batch", commit)
    assert store.list(USER) == []
    for prefix in ("c:", "m:", "a:", "r:", "v:", "t:"):
        assert store.repository.query(identity(USER), prefix + cid) == []


def test_blob_container_is_private_and_paths_not_client_controlled(store):
    from test_workspace import image_bytes

    assert store.storage.client.get_container_properties()["public_access"] is None
    cid = store.create(USER)["id"]
    a = store.upload(cid, USER, image_bytes(), "image/png", "../../unsafe.png")
    metadata = store.attachment(cid, a["id"], USER)
    assert metadata["filename"] == "unsafe.png"
    assert metadata["storage_reference"].startswith(
        f"attachments/{identity(USER)}/{cid}/"
    )
    with pytest.raises(StorageError):
        store.storage.read("../../outside")
    assert "storage_reference" not in store.get(cid, USER).get("messages", [])


def test_failed_blob_upload_cleans_reserved_metadata(store, monkeypatch):
    from test_workspace import image_bytes

    cid = store.create(USER)["id"]
    monkeypatch.setattr(
        store.storage, "put", lambda *_: (_ for _ in ()).throw(StorageError("failed"))
    )
    with pytest.raises(StorageError):
        store.upload(cid, USER, image_bytes(), "image/png", "image.png")
    assert store.repository.query(identity(USER), "a:" + cid + ":") == []
    assert store.owned(cid, USER).get("pending_id") is None


def test_project_delete_resume_detaches_without_deleting_chats(store, monkeypatch):
    cid = store.create(USER)["id"]
    pid = store.create_project(USER, "Project")["id"]
    store.metadata(cid, USER, {"project_id": pid, "is_pinned": True})
    commit = store.repository.batch

    def fail_detach(operations):
        if any(e["RowKey"] == "c:" + cid for _, e in operations):
            raise StorageError("failed")
        commit(operations)

    monkeypatch.setattr(store.repository, "batch", fail_detach)
    with pytest.raises(StorageError):
        store.change_project(pid, USER)
    assert store.project_owned(pid, USER, True)["deleting"]
    assert store.get(cid, USER)["project_id"] is None
    with pytest.raises(HTTPException):
        store.metadata(cid, USER, {"project_id": pid})
    monkeypatch.setattr(store.repository, "batch", commit)
    store.change_project(pid, USER)
    assert store.get(cid, USER)["is_pinned"]


def test_expired_upload_recovers_blob_and_metadata_before_next_turn(store):
    from test_workspace import image_bytes

    cid = store.create(USER)["id"]
    c = store.owned(cid, USER)
    aid = str(uuid4())
    reference = store.blob_prefix(c) + aid + ".png"
    a = store.record(
        identity(USER),
        f"a:{cid}:{aid}",
        id=aid,
        state="uploading",
        storage_reference=reference,
    )
    c.update(
        pending_id="upload:" + aid,
        pending_at=(now() - timedelta(seconds=121)).isoformat(),
    )
    store.repository.batch([("create", a), ("update", c)])
    store.storage.put(reference, image_bytes())
    attempt, *_ = store.start_stream(cid, USER, "recovered")
    assert store.repository.get(identity(USER), a["RowKey"]) is None
    with pytest.raises(StorageError):
        store.storage.read(reference)
    store.end_stream(cid, USER, attempt, "done", "completed")


def test_expired_discard_cannot_bind_retiring_image(store):
    from test_workspace import image_bytes

    cid = store.create(USER)["id"]
    uploaded = store.upload(cid, USER, image_bytes(), "image/png", "draft.png")
    a = store.attachment(cid, uploaded["id"], USER)
    a["state"] = "retiring"
    c = store.owned(cid, USER)
    c.update(
        pending_id="discard:" + a["id"],
        pending_at=(now() - timedelta(seconds=121)).isoformat(),
    )
    store.repository.batch([("update", c), ("update", a)])
    with pytest.raises(HTTPException) as error:
        store.start_stream(cid, USER, "bind", attachment_ids=[a["id"]])
    assert error.value.status_code == 404
    assert store.owned(cid, USER).get("pending_id") is None
    assert store.repository.query(identity(USER), "a:" + cid + ":") == []


def test_snapshot_read_retries_after_concurrent_update(store, monkeypatch):
    cid = store.create(USER)["id"]
    read = store.messages
    changed = False

    def race(c):
        nonlocal changed
        rows = read(c)
        if not changed:
            changed = True
            store.metadata(cid, USER, {"is_pinned": True})
        return rows

    monkeypatch.setattr(store, "messages", race)
    assert store.get(cid, USER)["is_pinned"]


def test_cross_partition_batch_rejected_before_network(store):
    with pytest.raises(ValueError):
        store.repository.batch(
            [("create", store.record("a", "x")), ("create", store.record("b", "y"))]
        )


def test_projects_list_resumes_tombstone_cleanup(store):
    cid = store.create(USER)["id"]
    pid = store.create_project(USER, "Project")["id"]
    store.metadata(cid, USER, {"project_id": pid})
    p = store.project_owned(pid, USER)
    p["deleting"] = True
    store.repository.batch([("update", p)])
    assert store.projects(USER) == []
    assert store.repository.get(identity(USER), "p:" + pid) is None
    assert store.get(cid, USER)["project_id"] is None
