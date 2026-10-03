"""Real Azurite integrations, isolated entities; pure unit tests need no emulator."""

import os
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import pytest
from app.storage.azure import AZURITE_CONNECTION, configured_storage

INTEGRATION_MODULES = {
    "test_api",
    "test_protection",
    "test_conversations",
    "test_chat_stream",
    "test_workspace",
    "test_table_storage",
}


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def azurite_services():
    # Launch our own process at ephemeral ports, never touch existing services/containers.
    ports = {name: free_port() for name in ("blob", "table", "queue")}
    connection = AZURITE_CONNECTION.replace(":10000/", f":{ports['blob']}/").replace(
        ":10002/", f":{ports['table']}/"
    )
    with (
        tempfile.TemporaryDirectory(prefix="openthread-test-azurite-") as directory,
        (Path(directory) / "startup.log").open("w+") as output,
    ):
        command = [
            "npm",
            "exec",
            "--yes",
            "--package",
            "azurite@3.35.0",
            "--",
            "azurite",
            "--location",
            directory,
            "--skipApiVersionCheck",
            "--silent",
        ]
        for name, port in ports.items():
            command += [f"--{name}Host", "127.0.0.1", f"--{name}Port", str(port)]
        process = subprocess.Popen(
            command, stdout=output, stderr=output, start_new_session=True
        )
        try:
            for _ in range(600):
                if process.poll() is not None:
                    raise RuntimeError(
                        "Test Azurite exited before startup. Install npm/Azurite."
                    )
                try:
                    with (
                        socket.create_connection(("127.0.0.1", ports["blob"]), 0.1),
                        socket.create_connection(("127.0.0.1", ports["table"]), 0.1),
                    ):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Test Azurite did not start within 60 seconds.")
            yield connection
        finally:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)


@pytest.fixture(autouse=True)
def storage_config(monkeypatch, request):
    monkeypatch.setenv("STORAGE_AUTH_MODE", "azurite")
    for key in (
        "CHAT_CONTEXT_MAX_MESSAGES",
        "CHAT_CONTEXT_MAX_BYTES",
        "CHAT_TOKEN_BUDGET",
        "CHAT_TOKEN_SAFETY_MARGIN",
    ):
        monkeypatch.delenv(key, raising=False)
    if request.module.__name__.split(".")[-1] not in INTEGRATION_MODULES:
        yield
        return
    connection = request.getfixturevalue("azurite_services")
    monkeypatch.setenv("AZURITE_CONNECTION_STRING", connection)
    monkeypatch.setenv("STORAGE_TABLE_NAME", "Test" + uuid4().hex)
    monkeypatch.setenv("STORAGE_BLOB_CONTAINER", "test-" + uuid4().hex)
    repo, blobs, _ = configured_storage()
    try:
        yield
    finally:
        repo.service.delete_table(repo.client.table_name)
        blobs.client.delete_container()
        repo.close()
        blobs.close()
