"""Official Azure SDKs live only here; same adapters serve Azurite and cloud."""

import os
from urllib.parse import urlsplit

from azure.core import MatchConditions
from azure.core.exceptions import (
    AzureError,
    HttpResponseError,
    ResourceExistsError,
    ResourceNotFoundError,
)
from azure.data.tables import TableServiceClient, UpdateMode
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

from app.storage.contracts import StorageConflict, StorageError

# Public, documented emulator credentials; not a cloud account key.
AZURITE_CONNECTION = "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;"


def failure(exc):
    if isinstance(exc, HttpResponseError) and exc.status_code in (409, 412):
        return StorageConflict("Storage changed concurrently. Retry the operation.")
    return StorageError("Workspace storage is unavailable.")


class TableRepository:
    def __init__(self, service, table):
        self.service = service
        self.client = service.get_table_client(table)

    def decode(self, entity):
        return {**entity, "_etag": entity.metadata["etag"]}

    def get(self, partition, row):
        try:
            return self.decode(self.client.get_entity(partition, row))
        except ResourceNotFoundError:
            return None
        except AzureError as exc:
            raise failure(exc) from None

    def query(self, partition, prefix):
        try:
            return [
                self.decode(e)
                for e in self.client.query_entities(
                    "PartitionKey eq @pk and RowKey ge @lo and RowKey lt @hi",
                    parameters={"pk": partition, "lo": prefix, "hi": prefix + "\uffff"},
                )
            ]
        except AzureError as exc:
            raise failure(exc) from None

    def batch(self, operations):
        if not operations or len(operations) > 100:
            raise ValueError("Atomic batch must have 1..100 operations.")
        if len({e["PartitionKey"] for _, e in operations}) != 1:
            raise ValueError("Atomic batch requires one partition.")
        converted = []
        for action, entity in operations:
            payload = {
                k: v for k, v in entity.items() if k != "_etag" and v is not None
            }
            options = {}
            if action in ("update", "delete"):
                options = {
                    "etag": entity["_etag"],
                    "match_condition": MatchConditions.IfNotModified,
                }
            if action == "update":
                options["mode"] = UpdateMode.REPLACE
            converted.append((action, payload, options))
        try:
            self.client.submit_transaction(converted)
        except AzureError as exc:
            raise failure(exc) from None

    def close(self):
        self.client.close()
        self.service.close()


class BlobStorage:
    def __init__(self, service, container):
        self.service = service
        self.client = service.get_container_client(container)

    def validate(self, reference):
        import re

        if not re.fullmatch(
            r"attachments/[a-f0-9]{64}/[a-f0-9-]{36}/[a-f0-9-]{36}\.png", reference
        ):
            raise StorageError("Invalid object reference.")

    def put(self, reference, content):
        self.validate(reference)
        try:
            self.client.upload_blob(
                reference,
                content,
                overwrite=False,
                content_settings=ContentSettings(content_type="image/png"),
                logging_enable=False,
            )
        except AzureError as exc:
            raise failure(exc) from None

    def read(self, reference):
        self.validate(reference)
        try:
            return self.client.download_blob(reference, logging_enable=False).readall()
        except AzureError as exc:
            raise failure(exc) from None

    def remove(self, reference):
        self.validate(reference)
        try:
            self.client.delete_blob(
                reference, delete_snapshots="include", logging_enable=False
            )
        except ResourceNotFoundError:
            pass
        except AzureError as exc:
            raise failure(exc) from None

    def remove_prefix(self, prefix):
        import re

        if not re.fullmatch(r"attachments/[a-f0-9]{64}/[a-f0-9-]{36}/", prefix):
            raise StorageError("Invalid object prefix.")
        try:
            for blob in self.client.list_blobs(name_starts_with=prefix):
                self.remove(blob.name)
        except AzureError as exc:
            raise failure(exc) from None

    def close(self):
        self.client.close()
        self.service.close()


def configured_storage():
    mode = os.getenv("STORAGE_AUTH_MODE", "").strip()
    if not mode:
        return None
    table = os.getenv("STORAGE_TABLE_NAME", "OpenThreadWorkspace")
    container = os.getenv("STORAGE_BLOB_CONTAINER", "attachments")
    credential = None
    if mode == "azurite":
        connection = os.getenv("AZURITE_CONNECTION_STRING", AZURITE_CONNECTION)
        # Emulator credentials must never target remote/cloud endpoints.
        fields = dict(
            field.split("=", 1) for field in connection.split(";") if "=" in field
        )
        if not all(key in fields for key in ("BlobEndpoint", "TableEndpoint")):
            raise ValueError(
                "Azurite requires explicit local Blob and Table endpoints."
            )
        for key in ("BlobEndpoint", "TableEndpoint"):
            endpoint = urlsplit(fields[key])
            if endpoint.scheme != "http" or endpoint.hostname not in (
                "127.0.0.1",
                "localhost",
                "azurite",
            ):
                raise ValueError("Azurite requires local HTTP endpoints.")
        tables = TableServiceClient.from_connection_string(
            connection,
            logging_enable=False,
            retry_total=0,
            connection_timeout=5,
            read_timeout=30,
        )
        blobs = BlobServiceClient.from_connection_string(
            connection,
            logging_enable=False,
            retry_total=0,
            connection_timeout=5,
            read_timeout=30,
        )
        tables.create_table_if_not_exists(table)
        try:
            blobs.create_container(container, public_access=None)
        except ResourceExistsError:
            pass
    elif mode == "managed_identity":
        account = os.environ["STORAGE_ACCOUNT_NAME"]
        table_url = os.getenv(
            "STORAGE_TABLE_ENDPOINT", f"https://{account}.table.core.windows.net"
        )
        blob_url = os.getenv(
            "STORAGE_BLOB_ENDPOINT", f"https://{account}.blob.core.windows.net"
        )
        for url in (table_url, blob_url):
            if urlsplit(url).scheme != "https":
                raise ValueError("Cloud storage requires HTTPS.")
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        tables = TableServiceClient(
            table_url,
            credential=credential,
            logging_enable=False,
            retry_total=0,
            connection_timeout=5,
            read_timeout=30,
        )
        blobs = BlobServiceClient(
            blob_url,
            credential=credential,
            logging_enable=False,
            retry_total=0,
            connection_timeout=5,
            read_timeout=30,
        )
    else:
        raise ValueError("STORAGE_AUTH_MODE must be azurite or managed_identity.")
    return TableRepository(tables, table), BlobStorage(blobs, container), credential
