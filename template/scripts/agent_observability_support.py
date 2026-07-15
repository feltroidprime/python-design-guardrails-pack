"""Private-file, JSON, and process boundaries for agent observability."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import cast


class OperatorError(RuntimeError):
    """An actionable setup or API failure safe to show to the operator."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Credentials:
    public_key: str
    secret_key: str
    base_url: str


def json_value(text: str) -> object:
    return cast("object", json.loads(text))


def object_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    mapping = cast("dict[object, object]", value)
    return {key: item for key, item in mapping.items() if isinstance(key, str)}


def object_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    entries = cast("list[object]", value)
    return [object_mapping(cast("object", entry)) for entry in entries if isinstance(entry, dict)]


def read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        return object_mapping(json_value(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise OperatorError(f"cannot read JSON config {path}: {error}") from error


def write_private_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            _ = stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        _ = temporary.replace(path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def run_command(
    command: tuple[str, ...],
    *,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    executable = shutil.which(command[0])
    if executable is None:
        raise OperatorError(f"required command is not installed: {command[0]}")
    completed = subprocess.run(
        [executable, *command[1:]],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no diagnostic"
        raise OperatorError(f"{command[0]} exited {completed.returncode}: {detail}")
    return completed


def pinned_checkout(
    root: Path,
    *,
    agent: str,
    repository: str,
    revision: str,
) -> Path:
    checkout = root / ".agent-observability" / f"{agent}-plugin-{revision}"
    if (checkout / ".git").is_dir():
        actual = run_command(("git", "rev-parse", "HEAD"), cwd=checkout).stdout.strip()
        cleanliness = run_command(
            ("git", "status", "--porcelain"),
            cwd=checkout,
        ).stdout.strip()
        if actual == revision and not cleanliness:
            return checkout
        shutil.rmtree(checkout)
    checkout.parent.mkdir(parents=True, exist_ok=True)
    _ = run_command(("git", "init", str(checkout)), cwd=root)
    _ = run_command(
        ("git", "-C", str(checkout), "fetch", "--depth", "1", repository, revision),
        cwd=root,
    )
    _ = run_command(("git", "-C", str(checkout), "checkout", "--detach", "FETCH_HEAD"), cwd=root)
    actual = run_command(("git", "rev-parse", "HEAD"), cwd=checkout).stdout.strip()
    if actual != revision:
        raise OperatorError(f"{agent} plugin checkout mismatch: {actual}")
    return checkout


def require_version(command: str, minimum: tuple[int, ...], root: Path) -> None:
    actual_text = run_command((command, "--version"), cwd=root).stdout
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", actual_text)
    if match is None:
        raise OperatorError(f"cannot parse tool version: {actual_text.strip()}")
    actual = tuple(int(part) for part in match.groups(default="0"))
    if actual < minimum:
        wanted = ".".join(str(part) for part in minimum)
        raise OperatorError(f"{command} {wanted}+ is required; found {actual_text.strip()}")
