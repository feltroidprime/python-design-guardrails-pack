"""Read complete coding-agent sessions back from the Langfuse public API."""

import base64
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
from typing import TYPE_CHECKING, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scripts.agent_observability_plugins import (
    credentials_from_project,
)
from scripts.agent_observability_support import (
    Credentials,
    OperatorError,
    json_value,
    object_list,
    object_mapping,
    write_private_json,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from http.client import HTTPResponse


MAX_DIAGNOSTIC_SAMPLES = 3
DIAGNOSTIC_PATTERN = re.compile(r"\b(?P<code>[A-Z]{1,5}\d{3,4})\b(?:[: ]+(?P<message>[^\r\n]+))?")


@dataclass(slots=True)
class DiagnosticTally:
    code: str
    occurrences: int = 0
    samples: list[str] = field(default_factory=list)
    session_ids: set[str] = field(default_factory=set)
    trace_ids: set[str] = field(default_factory=set)

    def record(self, *, message: str, session_id: str, trace_id: str) -> None:
        self.occurrences += 1
        if message and message not in self.samples and len(self.samples) < MAX_DIAGNOSTIC_SAMPLES:
            self.samples.append(message)
        if session_id:
            self.session_ids.add(session_id)
        if trace_id:
            self.trace_ids.add(trace_id)

    def json(self) -> dict[str, object]:
        return {
            "code": self.code,
            "occurrences": self.occurrences,
            "samples": self.samples,
            "session_count": len(self.session_ids),
            "trace_count": len(self.trace_ids),
        }


def _request_json(
    credentials: Credentials,
    endpoint: str,
    parameters: dict[str, str | int],
) -> dict[str, object]:
    query = f"?{urlencode(parameters)}" if parameters else ""
    token = base64.b64encode(f"{credentials.public_key}:{credentials.secret_key}".encode()).decode()
    request = Request(
        f"{credentials.base_url.rstrip('/')}{endpoint}{query}",
        headers={
            "Authorization": f"Basic {token}",
            "User-Agent": "agent-observability/1",
        },
    )
    try:
        response = cast("HTTPResponse", urlopen(request, timeout=10))
        with response:
            return object_mapping(json_value(response.read().decode("utf-8")))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise OperatorError(f"Langfuse API request failed: {error}") from error


def _belongs_to_repository(root: Path, trace: dict[str, object]) -> bool:
    metadata = object_mapping(trace.get("metadata"))
    if metadata.get("repository_root") == str(root):
        return True
    cwd = metadata.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return False
    candidate = Path(cwd).expanduser().resolve()
    return candidate == root or root in candidate.parents


def recent(root: Path, minutes: int) -> int:
    if minutes <= 0:
        raise OperatorError("recent-trace minutes must be positive")
    credentials = credentials_from_project(root)
    start = datetime.now(UTC) - timedelta(minutes=minutes)
    entries = [
        trace
        for trace in _recent_trace_details(credentials, start)
        if _belongs_to_repository(root, trace)
    ]
    entries.sort(key=lambda trace: str(trace.get("timestamp") or ""), reverse=True)
    if not entries:
        print("No Langfuse traces found in that window.")
        return 0
    for entry in entries[:20]:
        print(
            str(entry.get("timestamp") or "-"),
            str(entry.get("sessionId") or "-"),
            str(entry.get("name") or "-"),
            str(entry.get("id") or "-"),
        )
    return 0


def _trace_details(
    credentials: Credentials,
    parameters: dict[str, str | int],
) -> list[dict[str, object]]:
    page = 1
    details: list[dict[str, object]] = []
    while True:
        payload = _request_json(
            credentials,
            "/api/public/traces",
            {
                **parameters,
                "limit": 100,
                "orderBy": "timestamp.asc",
                "page": page,
            },
        )
        for summary in object_list(payload.get("data")):
            trace_id = summary.get("id")
            if isinstance(trace_id, str) and trace_id:
                details.append(_request_json(credentials, f"/api/public/traces/{trace_id}", {}))
        meta = object_mapping(payload.get("meta"))
        total_pages = meta.get("totalPages")
        if not isinstance(total_pages, int) or isinstance(total_pages, bool) or page >= total_pages:
            return details
        page += 1


def _session_traces(credentials: Credentials, session_id: str) -> list[dict[str, object]]:
    return _trace_details(credentials, {"sessionId": session_id})


def _recent_trace_details(
    credentials: Credentials,
    start: datetime,
) -> list[dict[str, object]]:
    return _trace_details(
        credentials,
        {"fromTimestamp": start.isoformat(timespec="milliseconds").replace("+00:00", "Z")},
    )


def _strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in object_mapping(cast("object", value)).values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in cast("list[object]", value):
            yield from _strings(item)


def _diagnostics(
    traces: list[dict[str, object]],
    minimum_sessions: int,
) -> list[dict[str, object]]:
    tallies: dict[str, DiagnosticTally] = {}
    for trace in traces:
        trace_id = trace.get("id")
        session_id = trace.get("sessionId")
        for text in _strings(trace):
            for match in DIAGNOSTIC_PATTERN.finditer(text):
                code = match.group("code")
                message = (match.group("message") or "").strip()
                tally = tallies.setdefault(code, DiagnosticTally(code=code))
                tally.record(
                    message=message,
                    session_id=session_id if isinstance(session_id, str) else "",
                    trace_id=trace_id if isinstance(trace_id, str) else "",
                )
    recurring = (tally for tally in tallies.values() if len(tally.session_ids) >= minimum_sessions)
    return [
        tally.json() for tally in sorted(recurring, key=lambda item: (-item.occurrences, item.code))
    ]


def _safe_session_slug(session_id: str) -> str:
    visible = re.sub(r"[^A-Za-z0-9_.-]+", "-", session_id).strip("-.")[:64]
    return f"{visible or hashlib.sha256(session_id.encode()).hexdigest()[:16]}.json"


def export_session(root: Path, session_id: str, output: Path | None) -> int:
    traces = [
        trace
        for trace in _session_traces(credentials_from_project(root), session_id)
        if _belongs_to_repository(root, trace)
    ]
    if not traces:
        raise OperatorError(f"Langfuse session has no traces for this repository: {session_id}")
    destination = output or (
        root / ".agent-observability" / "transcripts" / _safe_session_slug(session_id)
    )
    if not destination.is_absolute():
        destination = root / destination
    write_private_json(destination, {"session_id": session_id, "traces": traces})
    print(destination)
    return 0


def analyze(
    root: Path,
    minutes: int,
    minimum_sessions: int,
    output: Path | None,
) -> int:
    if minutes <= 0 or minimum_sessions <= 0:
        raise OperatorError("analysis minutes and minimum sessions must be positive")
    start = datetime.now(UTC) - timedelta(minutes=minutes)
    traces = [
        trace
        for trace in _recent_trace_details(credentials_from_project(root), start)
        if _belongs_to_repository(root, trace)
    ]
    diagnostics = _diagnostics(traces, minimum_sessions)
    sessions = {
        session_id
        for trace in traces
        if isinstance((session_id := trace.get("sessionId")), str) and session_id
    }
    destination = output or (root / ".agent-observability" / "analysis" / "latest.json")
    if not destination.is_absolute():
        destination = root / destination
    write_private_json(
        destination,
        {
            "diagnostics": diagnostics,
            "from_timestamp": start.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "generated_at": datetime.now(UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "session_count": len(sessions),
            "trace_count": len(traces),
            "traces": traces,
        },
    )
    print(f"Analyzed {len(traces)} traces across {len(sessions)} sessions.")
    for diagnostic in diagnostics:
        print(
            diagnostic["code"],
            f"{diagnostic['occurrences']} occurrences",
            f"across {diagnostic['session_count']} sessions",
        )
    print(destination)
    return 0
