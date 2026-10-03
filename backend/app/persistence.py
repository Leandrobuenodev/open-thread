"""Workspace operations over an entity repository and private object store."""

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, Request

from app.attachments import validate_image
from app.protection import ChatLimits, positive_integer
from app.storage.contracts import EntityRepository, ObjectStorage, StorageError
from app.token_budget import ContextBudget

CONTEXT_MESSAGES = 20
CONTEXT_BYTES = 16384
LEASE_SECONDS = 120


def now():
    return datetime.now(timezone.utc)


def stamp():
    return now().isoformat()


def identity(user):
    return hashlib.sha256((user.tenant_id + "\0" + user.object_id).encode()).hexdigest()


def attachment_data(a):
    return {
        k: a[k]
        for k in (
            "id",
            "media_type",
            "filename",
            "size",
            "width",
            "height",
            "created_at",
        )
    }


def summary(c):
    return {
        k: c.get(k)
        for k in ("id", "title", "created_at", "updated_at", "project_id", "is_pinned")
    }


def get_store(request: Request):
    store = request.app.state.conversation_store
    if store is None:
        raise HTTPException(503, "Conversation storage is not configured.")
    return store


class ConversationStore:
    def __init__(self, repository: EntityRepository, storage: ObjectStorage):
        self.repository = repository
        self.storage = storage
        self.budget = ContextBudget()
        self.context_messages = positive_integer(
            "CHAT_CONTEXT_MAX_MESSAGES", CONTEXT_MESSAGES
        )
        self.context_bytes = positive_integer("CHAT_CONTEXT_MAX_BYTES", CONTEXT_BYTES)
        if self.context_bytes < ChatLimits.from_environment().message_bytes:
            raise ValueError(
                "CHAT_CONTEXT_MAX_BYTES must accommodate CHAT_MAX_MESSAGE_BYTES."
            )

    def record(self, pk, row, **values):
        return {"PartitionKey": pk, "RowKey": row, "schema_version": 1, **values}

    def owned(self, cid, user, allow_deleting=False):
        c = self.repository.get(identity(user), "c:" + cid)
        if c is None or (c.get("deleting") and not allow_deleting):
            raise HTTPException(404, "Conversation not found.")
        return c

    def project_owned(self, pid, user, allow_deleting=False):
        p = self.repository.get(identity(user), "p:" + pid)
        if p is None or (p.get("deleting") and not allow_deleting):
            raise HTTPException(404, "Project not found.")
        return p

    def idle(self, c):
        if c.get("pending_id") and datetime.fromisoformat(
            c["pending_at"]
        ) > now() - timedelta(seconds=LEASE_SECONDS):
            raise HTTPException(409, "Conversation is processing a message.")

    def blob_prefix(self, c):
        return f"attachments/{c['PartitionKey']}/{c['id']}/"

    def create(self, user, conversation_id=None):
        cid = conversation_id or str(uuid4())
        c = self.record(
            identity(user),
            "c:" + cid,
            id=cid,
            title="New chat",
            created_at=stamp(),
            updated_at=stamp(),
            is_pinned=False,
            next_sequence=1,
        )
        self.repository.batch([("create", c)])
        return summary(c)

    def conversations(self, user):
        rows = self.repository.query(identity(user), "c:")
        for c in rows:
            if c.get("deleting"):
                self.delete(c["id"], user)
        return [c for c in rows if not c.get("deleting")]

    def visible_summary(self, c, user):
        data = summary(c)
        if c.get("project_id"):
            p = self.repository.get(identity(user), "p:" + c["project_id"])
            if not p or p.get("deleting"):
                data["project_id"] = None
        return data

    def list(self, user, offset=0):
        rows = sorted(
            self.conversations(user),
            key=lambda c: (c["updated_at"], c["id"]),
            reverse=True,
        )
        return [self.visible_summary(c, user) for c in rows[offset : offset + 50]]

    def library(self, user, offset=0):
        rows = [self.visible_summary(c, user) for c in self.conversations(user)]
        rows = [c for c in rows if c["is_pinned"] or c.get("project_id")]
        return sorted(rows, key=lambda c: (c["updated_at"], c["id"]), reverse=True)[
            offset : offset + 50
        ]

    def messages(self, c):
        pk = c["PartitionKey"]
        cid = c["id"]
        rows = self.repository.query(pk, "m:" + cid + ":")
        cuts = self.repository.query(pk, "v:" + cid + ":")
        replies = {
            r["prompt_id"]: r["assistant_id"]
            for r in self.repository.query(pk, "r:" + cid + ":")
        }
        attachments = self.repository.query(pk, "a:" + cid + ":")
        for m in rows:
            for cut in cuts:
                if cut["start"] <= m["sequence"] <= cut["end"]:
                    m["status"] = "superseded"
            if (
                m["role"] == "assistant"
                and m["status"] == "completed"
                and replies.get(m.get("reply_to_id"), m["id"]) != m["id"]
            ):
                m["status"] = "superseded"
            if m.get("parts"):
                m["content"] = "".join(
                    self.repository.get(pk, f"t:{cid}:{m['id']}:{i:03d}")["text"]
                    for i in range(m["parts"])
                )
            m["attachments"] = [
                attachment_data(a)
                for a in attachments
                if a.get("message_id") == m["id"] and a.get("state") == "ready"
            ]
        return sorted(rows, key=lambda m: m["sequence"])

    def message_data(self, m):
        return {
            k: m.get(k)
            for k in (
                "id",
                "role",
                "content",
                "created_at",
                "sequence",
                "status",
                "reply_to_id",
                "replaces_id",
                "attachments",
            )
        }

    def get(self, cid, user, before=None):
        for _ in range(3):
            c = self.owned(cid, user)
            rows = [
                m for m in self.messages(c) if before is None or m["sequence"] < before
            ][-100:]
            if self.owned(cid, user)["_etag"] == c["_etag"]:
                return {
                    **self.visible_summary(c, user),
                    "messages": [self.message_data(m) for m in rows],
                    "next_before": rows[0]["sequence"]
                    if rows and rows[0]["sequence"] > 1
                    else None,
                }
        from app.storage.contracts import StorageConflict

        raise StorageConflict("Conversation changed while reading. Retry.")

    def raw_message(self, c, mid):
        return next(
            (
                m
                for m in self.repository.query(c["PartitionKey"], "m:" + c["id"] + ":")
                if m["id"] == mid
            ),
            None,
        )

    def provider_message(self, c, m):
        images = [
            a
            for a in self.repository.query(c["PartitionKey"], "a:" + c["id"] + ":")
            if a.get("message_id") == m["id"] and a.get("state") == "ready"
        ]
        if not images:
            return {"role": m["role"], "content": m["content"]}
        parts = [{"type": "text", "text": m["content"]}] if m["content"] else []
        for a in images:
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64,"
                        + base64.b64encode(
                            self.storage.read(a["storage_reference"])
                        ).decode("ascii")
                    },
                }
            )
        return {"role": m["role"], "content": parts}

    def recover_objects(self, c, user):
        self.idle(c)
        rows = [
            a
            for a in self.repository.query(c["PartitionKey"], "a:" + c["id"] + ":")
            if not a.get("message_id") and a.get("state") != "ready"
        ]
        if not rows and not (c.get("pending_id") or "").startswith(
            ("upload:", "discard:", "recover:")
        ):
            return c
        reservation = "recover:" + str(uuid4())
        c.update(pending_id=reservation, pending_at=stamp())
        self.repository.batch([("update", c)])
        # ETag lease before any destructive Blob operation.
        for a in rows:
            self.storage.remove(a["storage_reference"])
        for offset in range(0, len(rows), 99):
            current = self.owned(c["id"], user)
            if current.get("pending_id") != reservation:
                raise StorageError("Cleanup reservation expired.")
            self.repository.batch(
                [("delete", a) for a in rows[offset : offset + 99]]
                + [("update", current)]
            )
        c = self.owned(c["id"], user)
        if c.get("pending_id") != reservation:
            raise StorageError("Cleanup reservation expired.")
        c.update(pending_id=None, pending_at=None)
        self.repository.batch([("update", c)])
        return self.owned(c["id"], user)

    def start_stream(self, cid, user, content=None, attachment_ids=(), edit_id=None):
        c = self.owned(cid, user)
        c = self.recover_objects(c, user)
        pk = c["PartitionKey"]
        rows = self.messages(c)
        ops = []
        attempt = str(uuid4())
        old = None
        if edit_id:
            old = next(
                (
                    m
                    for m in rows
                    if m["id"] == edit_id
                    and m["role"] == "user"
                    and m["status"] != "superseded"
                ),
                None,
            )
            if old is None:
                raise HTTPException(404, "Message not found.")
            ops.append(
                (
                    "create",
                    self.record(
                        pk,
                        f"v:{cid}:{attempt}",
                        start=old["sequence"],
                        end=c["next_sequence"] - 1,
                    ),
                )
            )
            for m in rows:
                if m["sequence"] >= old["sequence"]:
                    m["status"] = "superseded"
        for m in rows:
            if m["status"] == "pending":
                raw = self.raw_message(c, m["id"])
                raw["status"] = "failed"
                ops.append(("update", raw))
                m["status"] = "failed"
        if content is None:
            prompt = next(
                (
                    m
                    for m in reversed(rows)
                    if m["role"] == "user" and m["status"] != "superseded"
                ),
                None,
            )
            if prompt is None:
                raise HTTPException(409, "There is no response to regenerate.")
            content = prompt["content"]
        else:
            mid = str(uuid4())
            seq = c["next_sequence"]
            prompt = self.record(
                pk,
                f"m:{cid}:{seq:020d}:{mid}",
                id=mid,
                role="user",
                content=content,
                created_at=stamp(),
                updated_at=stamp(),
                sequence=seq,
                status="pending",
                replaces_id=edit_id,
                reply_to_id=None,
                attachments=[],
            )
            c["next_sequence"] += 1
            if seq == 1:
                c["title"] = content[:80] or "Image chat"
            ops.append(
                ("create", {k: v for k, v in prompt.items() if k != "attachments"})
            )
        images = []
        if len(attachment_ids) > 1:
            raise HTTPException(422, "At most one image per message.")
        for aid in attachment_ids:
            a = self.repository.get(pk, f"a:{cid}:{aid}")
            if not a or a.get("message_id") or a.get("state") != "ready":
                raise HTTPException(404, "Attachment not found.")
            a["message_id"] = prompt["id"]
            images.append(a)
            ops.append(("update", a))
        if old and not attachment_ids:
            for a in self.repository.query(pk, "a:" + cid + ":"):
                if a.get("message_id") == old["id"]:
                    copied = {
                        k: v for k, v in a.items() if k not in ("_etag", "RowKey")
                    }
                    copied["id"] = str(uuid4())
                    copied["RowKey"] = f"a:{cid}:{copied['id']}"
                    copied["message_id"] = prompt["id"]
                    images.append(copied)
                    ops.append(("create", copied))
        context = [
            self.provider_message(c, m)
            for m in rows
            if m["status"] == "completed" and m["sequence"] < prompt["sequence"]
        ][-self.context_messages + 1 :]
        current = self.provider_message(c, prompt)
        if images:
            parts = [{"type": "text", "text": content}] if content else []
            for a in images:
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64,"
                            + base64.b64encode(
                                self.storage.read(a["storage_reference"])
                            ).decode("ascii")
                        },
                    }
                )
            current = {"role": "user", "content": parts}
            prompt["attachments"] = [attachment_data(a) for a in images]
        context = self.budget.trim(context + [current], self.context_bytes)
        seq = c["next_sequence"]
        assistant = self.record(
            pk,
            f"m:{cid}:{seq:020d}:{attempt}",
            id=attempt,
            role="assistant",
            content="",
            created_at=stamp(),
            updated_at=stamp(),
            sequence=seq,
            status="pending",
            reply_to_id=prompt["id"],
        )
        c.update(
            next_sequence=seq + 1,
            pending_id=attempt,
            pending_at=stamp(),
            updated_at=stamp(),
        )
        ops.extend([("create", assistant), ("update", c)])
        self.repository.batch(ops)
        return (
            attempt,
            context,
            self.message_data(prompt),
            self.message_data({**assistant, "attachments": []}),
        )

    def end_stream(self, cid, user, attempt, content, status, legacy_failure=False):
        if status not in ("completed", "failed", "cancelled"):
            raise ValueError("Invalid attempt status.")
        c = self.owned(cid, user)
        if c.get("pending_id") != attempt:
            raise HTTPException(409, "Message attempt is no longer active.")
        assistant = self.raw_message(c, attempt)
        prompt = self.raw_message(c, assistant["reply_to_id"])
        pk = c["PartitionKey"]
        ops = []
        assistant.update(content=content, status=status, updated_at=stamp())
        # Table strings max 64 KiB UTF-16; split large outputs inside the same batch.
        if len(content) > 8000:
            chunks = [content[i : i + 8000] for i in range(0, len(content), 8000)]
            assistant.update(content="", parts=len(chunks))
            ops.extend(
                ("create", self.record(pk, f"t:{cid}:{attempt}:{i:03d}", text=text))
                for i, text in enumerate(chunks)
            )
        if status == "completed":
            prompt["status"] = "completed"
            key = f"r:{cid}:{prompt['id']}"
            reply = self.repository.get(pk, key)
            marker = reply or self.record(pk, key)
            marker.update(prompt_id=prompt["id"], assistant_id=attempt)
            ops.append(("update" if reply else "create", marker))
        elif prompt["status"] != "completed":
            prompt["status"] = status
        c.update(pending_id=None, pending_at=None, updated_at=stamp())
        if legacy_failure:
            c["next_sequence"] -= 1
        ops.extend(
            [
                ("update", prompt),
                ("delete" if legacy_failure else "update", assistant),
                ("update", c),
            ]
        )
        self.repository.batch(ops)
        return self.message_data({**assistant, "content": content, "attachments": []})

    def begin_turn(self, cid, user, content):
        attempt, context, *_ = self.start_stream(cid, user, content)
        return attempt, context

    def finish_turn(self, cid, user, attempt, answer=None):
        return self.end_stream(
            cid,
            user,
            attempt,
            answer or "",
            "completed" if answer is not None else "failed",
            legacy_failure=answer is None,
        )

    def create_project(self, user, name):
        pid = str(uuid4())
        p = self.record(
            identity(user),
            "p:" + pid,
            id=pid,
            name=name,
            created_at=stamp(),
            updated_at=stamp(),
        )
        self.repository.batch([("create", p)])
        return self.project_data(p)

    def project_data(self, p):
        return {k: p[k] for k in ("id", "name", "created_at", "updated_at")}

    def projects(self, user):
        rows = self.repository.query(identity(user), "p:")
        for p in rows:
            if p.get("deleting"):
                self.change_project(p["id"], user)
        return [
            self.project_data(p)
            for p in sorted(rows, key=lambda p: (p["name"], p["id"]))
            if not p.get("deleting")
        ]

    def change_project(self, pid, user, name=None):
        p = self.project_owned(pid, user, allow_deleting=name is None)
        if name is not None:
            p.update(name=name, updated_at=stamp())
            self.repository.batch([("update", p)])
            return self.project_data(p)
        p["deleting"] = True
        self.repository.batch([("update", p)])
        # Tombstone blocks new association; detach guarded in small same-partition batches.
        for c in self.repository.query(identity(user), "c:"):
            if c.get("project_id") == pid:
                c["project_id"] = None
                self.repository.batch([("update", c)])
        self.repository.batch([("delete", self.project_owned(pid, user, True))])

    def metadata(self, cid, user, values):
        c = self.owned(cid, user)
        ops = []
        if values.get("project_id"):
            p = self.project_owned(values["project_id"], user)
            ops.append(("update", p))  # ETag guard serializes deletion/association.
        c.update(values)
        ops.append(("update", c))
        self.repository.batch(ops)
        return summary(c)

    def delete(self, cid, user):
        c = self.owned(cid, user, True)
        if not c.get("deleting"):
            self.idle(c)
            c["deleting"] = True
            self.repository.batch([("update", c)])
        self.storage.remove_prefix(self.blob_prefix(c))
        for prefix in ("m:", "a:", "v:", "r:", "t:"):
            rows = self.repository.query(c["PartitionKey"], prefix + cid + ":")
            for i in range(0, len(rows), 99):
                c = self.owned(cid, user, True)
                self.repository.batch(
                    [("delete", r) for r in rows[i : i + 99]] + [("update", c)]
                )
        self.repository.batch([("delete", self.owned(cid, user, True))])

    def attachment(self, cid, aid, user):
        c = self.owned(cid, user)
        a = self.repository.get(c["PartitionKey"], f"a:{cid}:{aid}")
        if not a or a.get("state") != "ready":
            raise HTTPException(404, "Attachment not found.")
        return a

    def upload(self, cid, user, raw, media_type, filename):
        content, filename, width, height = validate_image(raw, media_type, filename)
        c = self.owned(cid, user)
        c = self.recover_objects(c, user)
        pk = c["PartitionKey"]
        aid = str(uuid4())
        reference = self.blob_prefix(c) + aid + ".png"
        a = self.record(
            pk,
            f"a:{cid}:{aid}",
            id=aid,
            filename=filename,
            media_type="image/png",
            storage_reference=reference,
            size=len(content),
            width=width,
            height=height,
            created_at=stamp(),
            state="uploading",
        )
        previous = [
            p
            for p in self.repository.query(pk, "a:" + cid + ":")
            if not p.get("message_id")
        ]
        for draft in previous:
            draft["state"] = "retiring"
        c.update(pending_id="upload:" + aid, pending_at=stamp())
        self.repository.batch(
            [("update", c), ("create", a)] + [("update", p) for p in previous]
        )
        # Durable reservation precedes Blob write; failed/crashed uploads stay discoverable.
        try:
            self.storage.put(reference, content)
            previous = [
                p
                for p in self.repository.query(pk, "a:" + cid + ":")
                if p["id"] != aid and not p.get("message_id")
            ]
            for old in previous:
                self.storage.remove(old["storage_reference"])
            c = self.owned(cid, user)
            if c.get("pending_id") != "upload:" + aid:
                raise StorageError("Upload reservation expired.")
            a = self.repository.get(pk, a["RowKey"])
            a["state"] = "ready"
            c.update(pending_id=None, pending_at=None)
            self.repository.batch(
                [("delete", p) for p in previous] + [("update", a), ("update", c)]
            )
            return attachment_data(a)
        except BaseException:
            # Keep metadata and reservation when cleanup fails; retry/delete can recover.
            self.storage.remove(reference)
            c = self.owned(cid, user)
            if c.get("pending_id") == "upload:" + aid:
                c.update(pending_id=None, pending_at=None)
                a = self.repository.get(pk, a["RowKey"])
                self.repository.batch([("delete", a), ("update", c)])
            raise

    def discard(self, cid, aid, user):
        c = self.owned(cid, user)
        self.idle(c)
        a = self.attachment(cid, aid, user)
        if a.get("message_id"):
            raise HTTPException(404, "Draft attachment not found.")
        # Reserve first so chat cannot bind a file while it is being removed.
        c.update(pending_id="discard:" + aid, pending_at=stamp())
        a["state"] = "retiring"
        self.repository.batch([("update", c), ("update", a)])
        a = self.repository.get(c["PartitionKey"], a["RowKey"])
        self.storage.remove(a["storage_reference"])
        c = self.owned(cid, user)
        c.update(pending_id=None, pending_at=None)
        self.repository.batch([("delete", a), ("update", c)])
