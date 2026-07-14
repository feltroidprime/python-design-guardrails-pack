#!/usr/bin/env python3
"""Minimal standard-library reference for the relay benchmark specification."""

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

STATES = ("queued", "running", "done", "failed")
JOB_FIELDS = ("id", "title", "note", "deadline", "state", "created_at", "updated_at")
EVENT_FIELDS = {"seq", "at", "type", "job_id", "data"}


class RelayError(Exception):
    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _timestamp(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise RelayError(f"{field} must be a UTC ISO-8601 datetime")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise RelayError(f"invalid {field}: {value!r}") from error
    return value


def _optional_deadline(value: object) -> str | None:
    if value is None or value == "":
        return None
    return _timestamp(value, field="deadline")


def _positive_id(value: object) -> int:
    if isinstance(value, bool):
        raise RelayError("id must be a positive integer")
    try:
        ident = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise RelayError("id must be a positive integer") from error
    if ident <= 0 or str(ident) != str(value):
        raise RelayError("id must be a positive integer")
    return ident


def _job_from_export(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict) or tuple(raw) != JOB_FIELDS:
        raise RelayError(f"job fields must be exactly: {', '.join(JOB_FIELDS)}")
    ident = _positive_id(raw["id"])
    title = raw["title"]
    note = raw["note"]
    state = raw["state"]
    if not isinstance(title, str) or not title.strip():
        raise RelayError("title must not be empty")
    if not isinstance(note, str):
        raise RelayError("note must be a string")
    if state not in STATES:
        raise RelayError(f"invalid state: {state!r}")
    return {
        "id": ident,
        "title": title,
        "note": note,
        "deadline": _optional_deadline(raw["deadline"]),
        "state": state,
        "created_at": _timestamp(raw["created_at"], field="created_at"),
        "updated_at": _timestamp(raw["updated_at"], field="updated_at"),
    }


def _enqueued_job(ident: int, at: str, data: object) -> dict[str, object]:
    if not isinstance(data, dict) or set(data) != {"title", "note", "deadline"}:
        raise RelayError("malformed enqueued event data")
    title = data["title"]
    note = data["note"]
    if not isinstance(title, str) or not title.strip() or not isinstance(note, str):
        raise RelayError("malformed enqueued event data")
    return {
        "id": ident,
        "title": title,
        "note": note,
        "deadline": _optional_deadline(data["deadline"]),
        "state": "queued",
        "created_at": at,
        "updated_at": at,
    }


def _load(log_path: Path) -> tuple[list[dict[str, object]], dict[int, dict[str, object]], dict[int, list[tuple[int, str, str, str]]]]:
    events: list[dict[str, object]] = []
    jobs: dict[int, dict[str, object]] = {}
    history: dict[int, list[tuple[int, str, str, str]]] = {}
    if not log_path.exists():
        return events, jobs, history
    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise RelayError(f"cannot read event log: {error}") from error
    for expected_seq, line in enumerate(lines, start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise RelayError(f"malformed event log at line {expected_seq}") from error
        if not isinstance(event, dict) or set(event) != EVENT_FIELDS:
            raise RelayError(f"malformed event at line {expected_seq}")
        if event["seq"] != expected_seq or isinstance(event["seq"], bool):
            raise RelayError(f"invalid event sequence at line {expected_seq}")
        at = _timestamp(event["at"], field="event time")
        ident = _positive_id(event["job_id"])
        event_type = event["type"]
        data = event["data"]
        if not isinstance(event_type, str):
            raise RelayError(f"invalid event type at line {expected_seq}")
        if event_type == "enqueued":
            if ident in jobs:
                raise RelayError(f"duplicate job id in event log: {ident}")
            jobs[ident] = _enqueued_job(ident, at, data)
        elif event_type == "imported":
            if ident in jobs or not isinstance(data, dict):
                raise RelayError(f"invalid imported event for id {ident}")
            exported = {"id": ident, **data}
            jobs[ident] = _job_from_export(exported)
        else:
            if data != {} or ident not in jobs:
                raise RelayError(f"invalid {event_type!r} event for id {ident}")
            expected_and_target = {
                "started": ("queued", "running"),
                "completed": ("running", "done"),
                "failed": ("running", "failed"),
                "retried": ("failed", "queued"),
            }.get(event_type)
            if expected_and_target is None:
                raise RelayError(f"unknown event type: {event_type}")
            expected, target = expected_and_target
            if jobs[ident]["state"] != expected:
                raise RelayError(f"illegal transition in event log for id {ident}")
            jobs[ident]["state"] = target
            jobs[ident]["updated_at"] = at
        resulting_state = str(jobs[ident]["state"])
        history.setdefault(ident, []).append((expected_seq, at, event_type, resulting_state))
        events.append(event)
    return events, jobs, history


def _append_events(log_path: Path, events: list[dict[str, object]]) -> None:
    if not events:
        return
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", newline="\n") as handle:
            for event in events:
                handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
                handle.write("\n")
    except OSError as error:
        raise RelayError(f"cannot append event log: {error}") from error


def _event(seq: int, at: str, event_type: str, ident: int, data: dict[str, object] | None = None) -> dict[str, object]:
    return {"seq": seq, "at": at, "type": event_type, "job_id": ident, "data": data or {}}


def _overdue(job: dict[str, object], now: str) -> bool:
    deadline = job["deadline"]
    return isinstance(deadline, str) and deadline < now and job["state"] in ("queued", "running")


def _exported(job: dict[str, object]) -> dict[str, object]:
    return {field: job[field] for field in JOB_FIELDS}


def _write_export(path: Path, output_format: str, jobs: list[dict[str, object]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if output_format == "json":
            payload = {"version": 1, "jobs": [_exported(job) for job in jobs]}
            path.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            return
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=JOB_FIELDS, lineterminator="\n")
            writer.writeheader()
            for job in jobs:
                row = _exported(job)
                if row["deadline"] is None:
                    row["deadline"] = ""
                writer.writerow(row)
    except OSError as error:
        raise RelayError(f"cannot write export: {error}") from error


def _read_import(path: Path, input_format: str) -> list[dict[str, object]]:
    try:
        if input_format == "json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or tuple(payload) != ("version", "jobs"):
                raise RelayError("invalid JSON export envelope")
            if payload["version"] != 1 or not isinstance(payload["jobs"], list):
                raise RelayError("unsupported JSON export")
            return [_job_from_export(raw) for raw in payload["jobs"]]
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != JOB_FIELDS:
                raise RelayError("invalid CSV header")
            return [_job_from_export(dict(row)) for row in reader]
    except RelayError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, csv.Error) as error:
        raise RelayError(f"cannot read import: {error}") from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="relay")
    parser.add_argument("--log", required=True)
    parser.add_argument("--now", required=True)
    commands = parser.add_subparsers(dest="command", required=True)

    enqueue = commands.add_parser("enqueue")
    enqueue.add_argument("--title", required=True)
    enqueue.add_argument("--note", default="")
    enqueue.add_argument("--deadline")

    for command in ("start", "done", "fail", "retry", "history"):
        transition = commands.add_parser(command)
        transition.add_argument("--id", required=True, type=int)

    listing = commands.add_parser("list")
    listing.add_argument("--state", choices=STATES)
    listing.add_argument("--overdue", action="store_true")
    commands.add_parser("stats")

    export = commands.add_parser("export")
    export.add_argument("--format", required=True, choices=("json", "csv"))
    export.add_argument("--output", required=True)
    import_command = commands.add_parser("import")
    import_command.add_argument("--format", required=True, choices=("json", "csv"))
    import_command.add_argument("--input", required=True)
    return parser


def _execute(args: argparse.Namespace) -> None:
    now = _timestamp(args.now, field="--now")
    log_path = Path(args.log)
    events, jobs, history = _load(log_path)
    ordered = [jobs[ident] for ident in sorted(jobs)]

    if args.command == "enqueue":
        if not args.title.strip():
            raise RelayError("title must not be empty")
        deadline = _optional_deadline(args.deadline)
        ident = max(jobs, default=0) + 1
        data = {"title": args.title, "note": args.note, "deadline": deadline}
        _append_events(log_path, [_event(len(events) + 1, now, "enqueued", ident, data)])
        print(f"id={ident}")
        return

    transitions = {
        "start": ("queued", "running", "started"),
        "done": ("running", "done", "completed"),
        "fail": ("running", "failed", "failed"),
        "retry": ("failed", "queued", "retried"),
    }
    if args.command in transitions:
        ident = args.id
        if ident not in jobs:
            raise RelayError(f"unknown job id: {ident}", exit_code=3)
        expected, _target, event_type = transitions[args.command]
        if jobs[ident]["state"] != expected:
            raise RelayError(
                f"cannot {args.command} job {ident} from state {jobs[ident]['state']}",
                exit_code=4,
            )
        _append_events(log_path, [_event(len(events) + 1, now, event_type, ident)])
        return

    if args.command == "list":
        for job in ordered:
            if args.state is not None and job["state"] != args.state:
                continue
            if args.overdue and not _overdue(job, now):
                continue
            deadline = job["deadline"] or "-"
            title = json.dumps(job["title"], ensure_ascii=False)
            note = json.dumps(job["note"], ensure_ascii=False)
            print(f"{job['id']}\t{job['state']}\t{deadline}\t{title}\t{note}")
        return

    if args.command == "history":
        ident = args.id
        if ident not in jobs:
            raise RelayError(f"unknown job id: {ident}", exit_code=3)
        for seq, at, event_type, state in history[ident]:
            print(f"{seq}\t{at}\t{event_type}\t{state}")
        return

    if args.command == "stats":
        counts = {state: 0 for state in STATES}
        for job in ordered:
            counts[str(job["state"])] += 1
        overdue = sum(_overdue(job, now) for job in ordered)
        print(
            f"queued={counts['queued']} running={counts['running']} "
            f"done={counts['done']} failed={counts['failed']} overdue={overdue}"
        )
        return

    if args.command == "export":
        _write_export(Path(args.output), args.format, ordered)
        print(f"exported={len(ordered)}")
        return

    if args.command == "import":
        imported_jobs = _read_import(Path(args.input), args.format)
        seen: set[int] = set()
        new_jobs: list[dict[str, object]] = []
        skipped = 0
        for job in imported_jobs:
            ident = int(job["id"])
            if ident in seen:
                raise RelayError(f"duplicate import id: {ident}")
            seen.add(ident)
            existing = jobs.get(ident)
            if existing is None:
                new_jobs.append(job)
            elif _exported(existing) == job:
                skipped += 1
            else:
                raise RelayError(f"import id {ident} conflicts with existing job")
        append = [
            _event(
                len(events) + offset,
                now,
                "imported",
                int(job["id"]),
                {field: job[field] for field in JOB_FIELDS if field != "id"},
            )
            for offset, job in enumerate(new_jobs, start=1)
        ]
        _append_events(log_path, append)
        print(f"imported={len(new_jobs)} skipped={skipped}")
        return

    raise RelayError(f"unsupported command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _execute(args)
    except RelayError as error:
        print(str(error), file=sys.stderr)
        return error.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
