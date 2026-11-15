"""Request log sinks: the optional BigQuery copy and fan-out isolation. No Google calls."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from app.core.config import Settings
from app.services.request_log import (
    METADATA_TOKEN_URL,
    BigQueryRequestLogSink,
    FanoutSink,
    MetadataToken,
    RequestEvent,
)

TABLE = "agentlane-demo.edge_logs.agent_requests"


def event(path="/product/trail-runner"):
    return RequestEvent(
        site_id=uuid4(),
        received_at=datetime(2026, 11, 15, 9, 30, tzinfo=UTC),
        agent="ChatGPT-User",
        agent_kind="agent",
        method="GET",
        path=path,
        status=200,
        duration_ms=41,
        served_by="variant",
        response_bytes=1830,
        client_hash="a" * 64,
        user_agent="ChatGPT-User/1.0",
        action=None,
    )


def test_bigquery_sink_streams_rows_with_a_cached_metadata_token():
    seen = []

    def handler(request: httpx.Request):
        seen.append(request)
        if str(request.url) == METADATA_TOKEN_URL:
            assert request.headers["metadata-flavor"] == "Google"
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(200, json={"kind": "bigquery#tableDataInsertAllResponse"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    sink = BigQueryRequestLogSink(TABLE, client=client)
    sink.write([event()])
    sink.write([event("/llms.txt")])

    inserts = [r for r in seen if r.url.host == "bigquery.googleapis.com"]
    assert len(seen) - len(inserts) == 1  # The token was fetched once and reused.
    assert inserts[0].url.path == (
        "/bigquery/v2/projects/agentlane-demo/datasets/edge_logs/tables/agent_requests/insertAll"
    )
    assert inserts[0].headers["authorization"] == "Bearer tok"
    row = json.loads(inserts[0].content)["rows"][0]
    assert row["insertId"]
    assert row["json"]["received_at"] == "2026-11-15T09:30:00+00:00"
    assert row["json"]["path"] == "/product/trail-runner"
    assert row["json"]["served_by"] == "variant"
    assert isinstance(row["json"]["site_id"], str)


def test_bigquery_row_errors_are_failures():
    def handler(request):
        return httpx.Response(200, json={"insertErrors": [{"index": 0, "errors": []}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    sink = BigQueryRequestLogSink(TABLE, client=client, token=lambda: "tok")
    with pytest.raises(ValueError, match="rejected 1 of 1"):
        sink.write([event()])


def test_metadata_token_errors_propagate():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    with pytest.raises(httpx.HTTPStatusError):
        MetadataToken(client)()


def test_fanout_keeps_writing_when_one_sink_fails():
    written = []

    class Broken:
        def write(self, events):
            raise httpx.ConnectError("down")

    class Memory:
        def write(self, events):
            written.extend(events)

    FanoutSink([Broken(), Memory()]).write([event()])
    assert len(written) == 1


@pytest.mark.parametrize(
    "table,valid",
    [
        (TABLE, True),
        ("", True),
        ("no-dots", False),
        ("Bad_Project.dataset.table", False),
        ("project.dataset", False),
    ],
)
def test_bigquery_table_setting_is_validated(table, valid):
    if valid:
        assert Settings(edge_bigquery_table=table).edge_bigquery_table == table
    else:
        with pytest.raises(ValueError):
            Settings(edge_bigquery_table=table)


def test_bigquery_schema_matches_the_logged_event():
    from dataclasses import fields
    from pathlib import Path

    schema = Path(__file__).resolve().parents[2] / "deploy/bigquery/agent_requests.schema.json"
    columns = {column["name"] for column in json.loads(schema.read_text())}
    assert columns == {field.name for field in fields(RequestEvent)}


def test_client_hash_is_keyed_even_without_a_configured_secret():
    import hashlib

    from pydantic import SecretStr

    from app.services.request_log import client_hash

    unkeyed = Settings(verification_secret=SecretStr(""))
    value = client_hash("203.0.113.7", unkeyed)
    assert value != hashlib.sha256(b"edge:203.0.113.7").hexdigest()
    assert value == client_hash("203.0.113.7", unkeyed)  # Stable within a process.
    keyed = Settings(verification_secret=SecretStr("operator-secret"))
    assert client_hash("203.0.113.7", keyed) != value
