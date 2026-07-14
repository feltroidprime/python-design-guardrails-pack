"""Langfuse adapter contract tests; local fake HTTP only, no SDK or network."""

import base64
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from benchmarks.e2e.config import LangfuseSettings
from benchmarks.e2e.exporting import ArmTrace, LangfuseExporter, TraceSpan


def test_langfuse_exporter_ingests_trace_spans_and_scores_in_one_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[tuple[str, str | None, dict[str, object]]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            body = self.rfile.read(int(self.headers["Content-Length"]))
            requests.append(
                (
                    self.path,
                    self.headers.get("Authorization"),
                    json.loads(body),
                )
            )
            response = b'{"successes":[{"id":"event","status":201}],"errors":[]}'
            self.send_response(207)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    trace = ArmTrace(
        run_id="fake-20260714T120000Z",
        arm="bare",
        name="benchmark:demo:bare",
        tags=("arm:bare", "template:v1.2.3", "variant:baseline"),
        metadata={
            "template": {"version": "v1.2.3", "variant": "baseline"},
            "app": "demo",
            "phase": "build",
            "pack_revision": "abc1234",
        },
        spans=(
            TraceSpan(name="instantiate", output={"seconds": 0.5}),
            TraceSpan(name="build", output={"duration_seconds": 1.2}),
        ),
        scores=(("probe_pass_rate", 1.0), ("cost_usd", 0.01)),
    )
    monkeypatch.setenv("BENCHMARK_LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("BENCHMARK_LANGFUSE_SECRET_KEY", "sk-lf-test")
    try:
        LangfuseExporter.from_settings(
            LangfuseSettings(
                enabled=True,
                public_key_env="BENCHMARK_LANGFUSE_PUBLIC_KEY",
                secret_key_env="BENCHMARK_LANGFUSE_SECRET_KEY",
                base_url=f"http://127.0.0.1:{server.server_port}",
                timeout_seconds=2.0,
            )
        ).export(trace)
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    assert len(requests) == 1
    path, authorization, payload = requests[0]
    assert path == "/api/public/ingestion"
    assert authorization == "Basic " + base64.b64encode(b"pk-lf-test:sk-lf-test").decode("ascii")
    batch = payload["batch"]
    assert [event["type"] for event in batch] == [
        "trace-create",
        "span-create",
        "span-create",
        "score-create",
        "score-create",
    ]
    trace_event = batch[0]
    assert trace_event["body"] == {
        "id": trace_event["body"]["id"],
        "name": "benchmark:demo:bare",
        "sessionId": "fake-20260714T120000Z",
        "version": "v1.2.3",
        "release": "abc1234",
        "tags": ["arm:bare", "template:v1.2.3", "variant:baseline"],
        "metadata": trace.metadata,
    }
    assert [event["body"]["name"] for event in batch[1:3]] == [
        "instantiate",
        "build",
    ]
    assert all(event["body"]["traceId"] == trace_event["body"]["id"] for event in batch[1:])
    assert [event["body"]["value"] for event in batch[3:]] == [1.0, 0.01]
    assert [event["body"]["name"] for event in batch[3:]] == [
        "probe_pass_rate",
        "cost_usd",
    ]
    assert all(event["body"]["dataType"] == "NUMERIC" for event in batch[3:])
