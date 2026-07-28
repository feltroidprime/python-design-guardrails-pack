#!/usr/bin/env python3
"""Collect fail-closed GitHub evidence and perform SHA-guarded PR merges.

This module shells out only to ``gh api``. Collection commands are read-only;
the sole mutation is the explicit ``merge-pr`` command.

Endpoint contracts:
https://docs.github.com/en/rest/pulls/pulls?apiVersion=2022-11-28
https://docs.github.com/en/rest/checks/runs?apiVersion=2022-11-28
https://docs.github.com/en/rest/commits/statuses?apiVersion=2022-11-28
https://docs.github.com/en/rest/repos/rules?apiVersion=2022-11-28
https://docs.github.com/en/graphql/reference/issues
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib
import json
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

API_VERSION = "2022-11-28"
PER_PAGE = 100
MAX_PR_FILES = 3000
PASSING_CONCLUSIONS = frozenset({"success", "neutral", "skipped"})
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
REPO_PART_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
REFONTE_REPO = "feltroidprime/conductor"
REFONTE_EPIC_NUMBER = 69

CLOSING_PRS_QUERY = """\
query ClosingPullRequests(
  $owner: String!
  $name: String!
  $number: Int!
  $cursor: String
) {
  repository(owner: $owner, name: $name) {
    issue(number: $number) {
      closedByPullRequestsReferences(
        first: 100
        after: $cursor
        includeClosedPrs: true
      ) {
        totalCount
        nodes {
          number
          url
          merged
          mergeCommit { oid }
          repository { nameWithOwner }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""

type Runner = Callable[
    [list[str], str | None],
    subprocess.CompletedProcess[str],
]


class EvidenceError(RuntimeError):
    """The requested evidence could not be proven."""


class GitHubAPIError(EvidenceError):
    """The GitHub CLI or REST response failed."""


def _default_runner(argv: list[str], stdin: str | None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
    )


def _runner_or_default(runner: Runner | None) -> Runner:
    return runner if runner is not None else _default_runner


def _api(
    method: str,
    endpoint: str,
    *,
    runner: Runner,
    query: Mapping[str, int | str] | None = None,
    body: Mapping[str, Any] | None = None,
) -> Any:
    if method not in {"GET", "POST", "PUT"}:
        raise AssertionError(f"unsupported internal GitHub method: {method}")
    if method == "GET" and body is not None:
        raise AssertionError("GET requests cannot carry a request body")
    argv = [
        "gh",
        "api",
        "--method",
        method,
        "-H",
        "Accept: application/vnd.github+json",
        "-H",
        f"X-GitHub-Api-Version: {API_VERSION}",
        endpoint,
    ]
    for key, value in sorted((query or {}).items()):
        argv.extend(["-F", f"{key}={value}"])
    stdin: str | None = None
    if body is not None:
        argv.extend(["--input", "-"])
        stdin = json.dumps(body, sort_keys=True, separators=(",", ":"))
    try:
        completed = runner(argv, stdin)
    except OSError as exc:
        raise GitHubAPIError(f"could not start gh api: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        if not detail:
            detail = f"exit code {completed.returncode}"
        raise GitHubAPIError(f"gh api {method} {endpoint} failed: {detail}")
    try:
        return json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise GitHubAPIError(f"gh api {method} {endpoint} did not return valid JSON") from exc


def _repo(value: Any, *, field: str = "repo") -> str:
    if not isinstance(value, str):
        raise EvidenceError(f"{field} must be an owner/repository string")
    parts = value.split("/")
    if (
        len(parts) != 2
        or not all(parts)
        or not all(REPO_PART_RE.fullmatch(part) for part in parts)
        or any(part in {".", ".."} for part in parts)
    ):
        raise EvidenceError(f"{field} must be an owner/repository string")
    return value


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise EvidenceError(f"{field} must be a positive integer")
    return value


def _non_negative_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise EvidenceError(f"{field} must be a non-negative integer")
    return value


def _full_sha(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or SHA_RE.fullmatch(value) is None:
        raise EvidenceError(f"{field} must be a full 40-character Git SHA")
    return value.lower()


def _string(value: Any, *, field: str, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value.strip()):
        qualifier = "non-empty " if nonempty else ""
        raise EvidenceError(f"{field} must be a {qualifier}string")
    return value


def _object(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise EvidenceError(f"{field} must be an object")
    return value


def _array(value: Any, *, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise EvidenceError(f"{field} must be an array")
    return value


def _timestamp(value: Any, *, field: str) -> str:
    text = _string(value, field=field)
    if not text.endswith("Z"):
        raise EvidenceError(f"{field} must be a UTC GitHub timestamp")
    try:
        datetime.fromisoformat(text.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise EvidenceError(f"{field} must be a UTC GitHub timestamp") from exc
    return text


def _exact_keys(value: Mapping[str, Any], expected: set[str], *, field: str) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing:
        raise EvidenceError(f"{field} is missing keys: {', '.join(missing)}")
    if unknown:
        raise EvidenceError(f"{field} has unknown keys: {', '.join(unknown)}")


def _github_repo_from_api_url(value: Any) -> str:
    text = _string(value, field="GitHub issue repository_url")
    parsed = urlparse(text)
    parts = parsed.path.strip("/").split("/")
    if (
        parsed.scheme != "https"
        or parsed.netloc.casefold() != "api.github.com"
        or len(parts) != 3
        or parts[0] != "repos"
    ):
        raise EvidenceError("GitHub issue repository_url is not a github.com repository URL")
    return _repo("/".join(parts[1:]), field="GitHub issue repository")


def _same_repo(expected: str, actual: str, *, field: str) -> None:
    if expected.casefold() != actual.casefold():
        raise EvidenceError(f"{field} {actual!r} does not match requested repo {expected!r}")


def collect_issue(
    repo: str,
    number: int,
    *,
    runner: Runner | None = None,
) -> dict[str, Any]:
    """Collect one normalized issue directly from GitHub."""

    requested_repo = _repo(repo)
    requested_number = _positive_int(number, field="issue number")
    raw = _object(
        _api(
            "GET",
            f"repos/{requested_repo}/issues/{requested_number}",
            runner=_runner_or_default(runner),
        ),
        field="GitHub issue response",
    )
    if "pull_request" in raw:
        raise EvidenceError(f"{requested_repo}#{requested_number} is a pull request, not an issue")
    actual_repo = _github_repo_from_api_url(raw.get("repository_url"))
    _same_repo(requested_repo, actual_repo, field="GitHub issue repo")
    actual_number = _positive_int(raw.get("number"), field="GitHub issue number")
    if actual_number != requested_number:
        raise EvidenceError(
            f"GitHub issue number {actual_number} does not match requested issue {requested_number}"
        )
    state = _string(raw.get("state"), field="GitHub issue state")
    if state not in {"open", "closed"}:
        raise EvidenceError(f"unsupported GitHub issue state: {state}")
    title = _string(raw.get("title"), field="GitHub issue title")
    raw_body = raw.get("body")
    body = "" if raw_body is None else _string(raw_body, field="GitHub issue body", nonempty=False)
    labels_raw = _array(raw.get("labels"), field="GitHub issue labels")
    labels: list[str] = []
    for index, item in enumerate(labels_raw):
        label = _object(item, field=f"GitHub issue labels[{index}]")
        labels.append(_string(label.get("name"), field=f"GitHub issue labels[{index}].name"))
    updated_at = _timestamp(raw.get("updated_at"), field="GitHub issue updated_at")
    snapshot = {
        "schema_version": 1,
        "kind": "github_issue_snapshot",
        "source": "github",
        "repo": actual_repo,
        "number": actual_number,
        "state": state,
        "title": title,
        "body": body,
        "labels": sorted(set(labels)),
        "updated_at": updated_at,
        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
    }
    validate_issue_snapshot(snapshot)
    return snapshot


ISSUE_SNAPSHOT_KEYS = {
    "schema_version",
    "kind",
    "source",
    "repo",
    "number",
    "state",
    "title",
    "body",
    "labels",
    "updated_at",
    "body_sha256",
}


def validate_issue_snapshot(snapshot: Mapping[str, Any]) -> None:
    """Validate the closed normalized issue-snapshot schema."""

    value = _object(snapshot, field="issue snapshot")
    _exact_keys(value, ISSUE_SNAPSHOT_KEYS, field="issue snapshot")
    if isinstance(value["schema_version"], bool) or value["schema_version"] != 1:
        raise EvidenceError("issue snapshot schema_version must be 1")
    if value["kind"] != "github_issue_snapshot" or value["source"] != "github":
        raise EvidenceError("issue snapshot provenance is invalid")
    _repo(value["repo"], field="issue snapshot repo")
    _positive_int(value["number"], field="issue snapshot number")
    if value["state"] not in {"open", "closed"}:
        raise EvidenceError("issue snapshot state must be open or closed")
    _string(value["title"], field="issue snapshot title")
    body = _string(value["body"], field="issue snapshot body", nonempty=False)
    labels = _array(value["labels"], field="issue snapshot labels")
    if not all(isinstance(label, str) and label for label in labels):
        raise EvidenceError("issue snapshot labels must contain non-empty strings")
    if labels != sorted(set(labels)):
        raise EvidenceError("issue snapshot labels must be sorted and unique")
    _timestamp(value["updated_at"], field="issue snapshot updated_at")
    expected_digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if value["body_sha256"] != expected_digest:
        raise EvidenceError("issue snapshot body_sha256 does not match body")


REFONTE_EPIC_KEYS = {
    "repo",
    "number",
    "state",
    "title",
    "body",
    "updated_at",
    "url",
}
REFONTE_ISSUE_KEYS = {
    "repo",
    "number",
    "state",
    "state_reason",
    "title",
    "body",
    "labels",
    "updated_at",
    "url",
}
REFONTE_CLOSING_PR_KEYS = {"base_ref", "merge_sha", "url"}


def _safe_changed_path(value: Any, *, field: str) -> str:
    path = _string(value, field=field)
    parts = path.split("/")
    if (
        path.startswith("/")
        or "\\" in path
        or "\x00" in path
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise EvidenceError(f"{field} is not a safe repository-relative path")
    return path


def _paginated_arrays(
    endpoint: str,
    *,
    runner: Runner,
    field: str,
) -> list[Any]:
    result: list[Any] = []
    page = 1
    while True:
        current = _array(
            _api(
                "GET",
                endpoint,
                runner=runner,
                query={"page": page, "per_page": PER_PAGE},
            ),
            field=f"{field} page {page}",
        )
        if len(current) > PER_PAGE:
            raise EvidenceError(f"{field} page {page} exceeded GitHub page size")
        result.extend(current)
        if len(current) < PER_PAGE:
            return result
        page += 1


def _collect_changed_files(
    repo: str,
    number: int,
    *,
    expected_total: int,
    runner: Runner,
) -> list[str]:
    if expected_total >= MAX_PR_FILES:
        raise EvidenceError(
            "GitHub's PR-files endpoint caps results at 3000; "
            f"cannot prove a complete census of {expected_total} files"
        )
    raw_files = _paginated_arrays(
        f"repos/{repo}/pulls/{number}/files",
        runner=runner,
        field="GitHub PR files",
    )
    files: list[str] = []
    for index, raw_file in enumerate(raw_files):
        item = _object(raw_file, field=f"GitHub PR files[{index}]")
        files.append(
            _safe_changed_path(
                item.get("filename"),
                field=f"GitHub PR files[{index}].filename",
            )
        )
    if len(files) != len(set(files)):
        raise EvidenceError("GitHub PR files response contains duplicate filenames")
    if len(files) != expected_total:
        raise EvidenceError(
            f"GitHub PR declared {expected_total} changed files but pagination returned "
            f"{len(files)}"
        )
    return sorted(files)


def _required_check(
    context: Any,
    app_id: Any,
    *,
    field: str,
) -> tuple[str, int | None]:
    name = _string(context, field=f"{field}.context")
    if app_id is None or app_id == -1:
        return name, None
    return name, _positive_int(app_id, field=f"{field}.app_id")


def _branch_requirements(
    repo: str,
    base_ref: str,
    *,
    runner: Runner,
) -> set[tuple[str, int | None]]:
    encoded_ref = quote(base_ref, safe="")
    raw = _object(
        _api(
            "GET",
            f"repos/{repo}/branches/{encoded_ref}",
            runner=runner,
        ),
        field="GitHub base branch response",
    )
    if raw.get("name") != base_ref:
        raise EvidenceError("GitHub base branch response does not match PR base ref")
    protection = raw.get("protection")
    if protection is None:
        return set()
    protection_value = _object(protection, field="GitHub base branch protection")
    status_checks = protection_value.get("required_status_checks")
    if status_checks is None:
        return set()
    checks_value = _object(
        status_checks,
        field="GitHub base branch required_status_checks",
    )
    requirements: set[tuple[str, int | None]] = set()
    checks = checks_value.get("checks", [])
    for index, raw_check in enumerate(_array(checks, field="GitHub branch required checks")):
        check = _object(raw_check, field=f"GitHub branch required checks[{index}]")
        requirements.add(
            _required_check(
                check.get("context"),
                check.get("app_id"),
                field=f"GitHub branch required checks[{index}]",
            )
        )
    names_with_check_records = {name for name, _ in requirements}
    contexts = checks_value.get("contexts", [])
    for index, context in enumerate(_array(contexts, field="GitHub branch required contexts")):
        name = _string(context, field=f"GitHub branch required contexts[{index}]")
        if name not in names_with_check_records:
            requirements.add((name, None))
    return requirements


def _ruleset_requirements(
    repo: str,
    base_ref: str,
    *,
    runner: Runner,
) -> set[tuple[str, int | None]]:
    rules = _paginated_arrays(
        f"repos/{repo}/rules/branches/{quote(base_ref, safe='')}",
        runner=runner,
        field="GitHub active branch rules",
    )
    requirements: set[tuple[str, int | None]] = set()
    for rule_index, raw_rule in enumerate(rules):
        rule = _object(raw_rule, field=f"GitHub active branch rules[{rule_index}]")
        rule_type = _string(
            rule.get("type"),
            field=f"GitHub active branch rules[{rule_index}].type",
        )
        if rule_type in {"workflows", "merge_queue"}:
            raise EvidenceError(
                f"active {rule_type} rule is not representable as head-SHA status checks"
            )
        if rule_type != "required_status_checks":
            continue
        parameters = _object(
            rule.get("parameters"),
            field=f"GitHub active branch rules[{rule_index}].parameters",
        )
        raw_checks = _array(
            parameters.get("required_status_checks"),
            field=(f"GitHub active branch rules[{rule_index}].parameters.required_status_checks"),
        )
        for check_index, raw_check in enumerate(raw_checks):
            check = _object(
                raw_check,
                field=f"GitHub ruleset required checks[{rule_index}][{check_index}]",
            )
            requirements.add(
                _required_check(
                    check.get("context"),
                    check.get("integration_id"),
                    field=f"GitHub ruleset required checks[{rule_index}][{check_index}]",
                )
            )
    return requirements


def _collapse_requirements(
    requirements: set[tuple[str, int | None]],
) -> set[tuple[str, int | None]]:
    """Remove an any-app duplicate when a stricter requirement exists."""

    names_with_specific_app = {name for name, app_id in requirements if app_id is not None}
    return {
        (name, app_id)
        for name, app_id in requirements
        if app_id is not None or name not in names_with_specific_app
    }


def _collect_check_runs(
    repo: str,
    head_sha: str,
    *,
    runner: Runner,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    page = 1
    total_count: int | None = None
    seen_ids: set[int] = set()
    while True:
        raw = _object(
            _api(
                "GET",
                f"repos/{repo}/commits/{head_sha}/check-runs",
                runner=runner,
                query={"filter": "latest", "page": page, "per_page": PER_PAGE},
            ),
            field=f"GitHub check-runs page {page}",
        )
        current_total = _non_negative_int(
            raw.get("total_count"),
            field=f"GitHub check-runs page {page}.total_count",
        )
        if total_count is None:
            total_count = current_total
        elif current_total != total_count:
            raise EvidenceError("GitHub check-runs total_count changed during pagination")
        runs = _array(
            raw.get("check_runs"),
            field=f"GitHub check-runs page {page}.check_runs",
        )
        if len(runs) > PER_PAGE:
            raise EvidenceError(f"GitHub check-runs page {page} exceeded page size")
        for index, raw_run in enumerate(runs):
            run = _object(
                raw_run,
                field=f"GitHub check-runs page {page}[{index}]",
            )
            run_id = _positive_int(run.get("id"), field="GitHub check run id")
            if run_id in seen_ids:
                raise EvidenceError(f"GitHub check-runs repeated run id {run_id}")
            seen_ids.add(run_id)
            run_head = _full_sha(run.get("head_sha"), field="GitHub check run head_sha")
            if run_head != head_sha:
                raise EvidenceError(
                    f"check run {run_id} belongs to a different head SHA {run_head}"
                )
            app = run.get("app")
            app_id: int | None = None
            if app is not None:
                app_value = _object(app, field=f"GitHub check run {run_id}.app")
                app_id = _positive_int(
                    app_value.get("id"),
                    field=f"GitHub check run {run_id}.app.id",
                )
            details_url = run.get("details_url")
            if details_url is None:
                details_url = ""
            else:
                details_url = _string(
                    details_url,
                    field=f"GitHub check run {run_id}.details_url",
                    nonempty=False,
                )
            conclusion = run.get("conclusion")
            if conclusion is not None:
                conclusion = _string(
                    conclusion,
                    field=f"GitHub check run {run_id}.conclusion",
                )
            result.append(
                {
                    "id": run_id,
                    "name": _string(
                        run.get("name"),
                        field=f"GitHub check run {run_id}.name",
                    ),
                    "app_id": app_id,
                    "head_sha": run_head,
                    "status": _string(
                        run.get("status"),
                        field=f"GitHub check run {run_id}.status",
                    ),
                    "conclusion": conclusion,
                    "details_url": details_url,
                }
            )
        if len(runs) < PER_PAGE:
            break
        page += 1
    assert total_count is not None
    if len(result) != total_count:
        raise EvidenceError(
            f"GitHub reported {total_count} check runs but pagination returned {len(result)}"
        )
    return result


def _collect_commit_statuses(
    repo: str,
    head_sha: str,
    *,
    runner: Runner,
) -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    total_count: int | None = None
    page = 1
    while True:
        raw = _object(
            _api(
                "GET",
                f"repos/{repo}/commits/{head_sha}/status",
                runner=runner,
                query={"page": page, "per_page": PER_PAGE},
            ),
            field=f"GitHub combined status page {page}",
        )
        status_head = _full_sha(
            raw.get("sha"),
            field=f"GitHub combined status page {page}.sha",
        )
        if status_head != head_sha:
            raise EvidenceError(
                f"combined commit status belongs to a different head SHA {status_head}"
            )
        current_total = _non_negative_int(
            raw.get("total_count"),
            field=f"GitHub combined status page {page}.total_count",
        )
        if total_count is None:
            total_count = current_total
        elif total_count != current_total:
            raise EvidenceError("GitHub combined status total_count changed during pagination")
        page_statuses = _array(
            raw.get("statuses"),
            field=f"GitHub combined status page {page}.statuses",
        )
        if len(page_statuses) > PER_PAGE:
            raise EvidenceError(f"GitHub combined status page {page} exceeded page size")
        for index, raw_status in enumerate(page_statuses):
            status = _object(
                raw_status,
                field=f"GitHub combined status page {page}[{index}]",
            )
            status_id = _positive_int(status.get("id"), field="GitHub commit status id")
            if status_id in seen_ids:
                raise EvidenceError(f"GitHub combined statuses repeated status id {status_id}")
            seen_ids.add(status_id)
            item_sha = status.get("sha")
            if item_sha is not None:
                normalized_item_sha = _full_sha(
                    item_sha,
                    field=f"GitHub commit status {status_id}.sha",
                )
                if normalized_item_sha != head_sha:
                    raise EvidenceError(
                        f"commit status {status_id} belongs to a different head SHA "
                        f"{normalized_item_sha}"
                    )
            target_url = status.get("target_url")
            if target_url is None:
                target_url = ""
            else:
                target_url = _string(
                    target_url,
                    field=f"GitHub commit status {status_id}.target_url",
                    nonempty=False,
                )
            statuses.append(
                {
                    "id": status_id,
                    "name": _string(
                        status.get("context"),
                        field=f"GitHub commit status {status_id}.context",
                    ),
                    "head_sha": head_sha,
                    "state": _string(
                        status.get("state"),
                        field=f"GitHub commit status {status_id}.state",
                    ),
                    "details_url": target_url,
                }
            )
        if len(page_statuses) < PER_PAGE:
            break
        page += 1
    assert total_count is not None
    if len(statuses) != total_count:
        raise EvidenceError(
            f"GitHub reported {total_count} commit statuses but pagination returned {len(statuses)}"
        )
    return statuses


def _resolve_required_checks(
    requirements: set[tuple[str, int | None]],
    check_runs: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for name, required_app_id in sorted(
        requirements,
        key=lambda item: (item[0], -1 if item[1] is None else item[1]),
    ):
        run_candidates = [
            run
            for run in check_runs
            if run["name"] == name and (required_app_id is None or run["app_id"] == required_app_id)
        ]
        status_candidates = (
            [status for status in statuses if status["name"] == name]
            if required_app_id is None
            else []
        )
        candidates = [("check_run", candidate) for candidate in run_candidates] + [
            ("commit_status", candidate) for candidate in status_candidates
        ]
        if not candidates:
            suffix = "" if required_app_id is None else f" from GitHub App {required_app_id}"
            raise EvidenceError(f"required check {name}{suffix} is missing")
        if len(candidates) != 1:
            raise EvidenceError(
                f"required check {name} is ambiguous across {len(candidates)} providers"
            )
        source, candidate = candidates[0]
        if source == "check_run":
            status = candidate["status"]
            conclusion = candidate["conclusion"]
            if status != "completed" or conclusion not in PASSING_CONCLUSIONS:
                raise EvidenceError(
                    f"required check {name} did not pass (status={status}, conclusion={conclusion})"
                )
            app_id = candidate["app_id"]
        else:
            state = candidate["state"]
            status = "completed" if state != "pending" else "in_progress"
            conclusion = state
            if state != "success":
                raise EvidenceError(f"required check {name} did not pass (commit status={state})")
            app_id = None
        resolved.append(
            {
                "name": name,
                "required_app_id": required_app_id,
                "source": source,
                "id": candidate["id"],
                "app_id": app_id,
                "head_sha": candidate["head_sha"],
                "status": status,
                "conclusion": conclusion,
                "details_url": candidate["details_url"],
            }
        )
    return resolved


def _verify_pr_still_pinned(
    repo: str,
    number: int,
    *,
    head_sha: str,
    base_ref: str,
    changed_files_total: int,
    runner: Runner,
) -> None:
    current = _object(
        _api(
            "GET",
            f"repos/{repo}/pulls/{number}",
            runner=runner,
        ),
        field="GitHub PR verification response",
    )
    current_number = _positive_int(
        current.get("number"),
        field="GitHub PR verification number",
    )
    current_head = _object(current.get("head"), field="GitHub PR verification head")
    current_base = _object(current.get("base"), field="GitHub PR verification base")
    current_base_repo = _object(
        current_base.get("repo"),
        field="GitHub PR verification base.repo",
    )
    current_repo = _repo(
        current_base_repo.get("full_name"),
        field="GitHub PR verification repo",
    )
    current_sha = _full_sha(
        current_head.get("sha"),
        field="GitHub PR verification head SHA",
    )
    current_file_count = _non_negative_int(
        current.get("changed_files"),
        field="GitHub PR verification changed_files",
    )
    if (
        current_number != number
        or current_repo.casefold() != repo.casefold()
        or current_sha != head_sha
        or current.get("state") != "open"
        or current.get("mergeable") is not True
        or current_base.get("ref") != base_ref
        or current_file_count != changed_files_total
    ):
        raise EvidenceError("PR changed during evidence collection; discard the snapshot")


REQUIRED_CHECK_KEYS = {
    "name",
    "required_app_id",
    "source",
    "id",
    "app_id",
    "head_sha",
    "status",
    "conclusion",
    "details_url",
}
CI_KEYS = {"head_sha", "state", "url"}
PR_SNAPSHOT_KEYS = {
    "schema_version",
    "kind",
    "source",
    "repo",
    "number",
    "pr_url",
    "state",
    "head_sha",
    "base_ref",
    "mergeable",
    "changed_files",
    "changed_files_total",
    "changed_files_complete",
    "required_checks",
    "declarations",
    "ci",
}


def collect_pr_ci(
    repo: str,
    number: int,
    *,
    expected_head_sha: str,
    runner: Runner | None = None,
) -> dict[str, Any]:
    """Collect a complete PR/file/required-CI snapshot for one pinned head SHA."""

    requested_repo = _repo(repo)
    requested_number = _positive_int(number, field="PR number")
    expected_head = _full_sha(expected_head_sha, field="expected head SHA")
    run = _runner_or_default(runner)
    raw = _object(
        _api(
            "GET",
            f"repos/{requested_repo}/pulls/{requested_number}",
            runner=run,
        ),
        field="GitHub PR response",
    )
    actual_number = _positive_int(raw.get("number"), field="GitHub PR number")
    if actual_number != requested_number:
        raise EvidenceError(
            f"GitHub PR number {actual_number} does not match requested PR {requested_number}"
        )
    base = _object(raw.get("base"), field="GitHub PR base")
    base_repo = _object(base.get("repo"), field="GitHub PR base.repo")
    actual_repo = _repo(base_repo.get("full_name"), field="GitHub PR base repo")
    _same_repo(requested_repo, actual_repo, field="GitHub PR repo")
    head = _object(raw.get("head"), field="GitHub PR head")
    head_sha = _full_sha(head.get("sha"), field="GitHub PR head SHA")
    if head_sha != expected_head:
        raise EvidenceError(
            f"PR head SHA {head_sha} does not match expected head SHA {expected_head}"
        )
    state = _string(raw.get("state"), field="GitHub PR state")
    if state != "open":
        raise EvidenceError(f"GitHub PR must be open, got {state}")
    if raw.get("draft") is True:
        raise EvidenceError("GitHub PR is still a draft")
    mergeable = raw.get("mergeable")
    if mergeable is not True:
        raise EvidenceError(f"GitHub PR is not currently mergeable (mergeable={mergeable!r})")
    base_ref = _string(base.get("ref"), field="GitHub PR base ref")
    pr_url = _string(raw.get("html_url"), field="GitHub PR URL")
    expected_pr_url = f"https://github.com/{actual_repo}/pull/{actual_number}"
    if pr_url.casefold() != expected_pr_url.casefold():
        raise EvidenceError("GitHub PR URL does not match requested repo and PR number")
    declared_files = _non_negative_int(
        raw.get("changed_files"),
        field="GitHub PR changed_files",
    )
    changed_files = _collect_changed_files(
        actual_repo,
        actual_number,
        expected_total=declared_files,
        runner=run,
    )
    requirements = _branch_requirements(actual_repo, base_ref, runner=run)
    requirements.update(_ruleset_requirements(actual_repo, base_ref, runner=run))
    requirements = _collapse_requirements(requirements)
    if not requirements:
        raise EvidenceError(
            f"no required status checks are configured for {actual_repo}:{base_ref}"
        )
    check_runs = _collect_check_runs(actual_repo, head_sha, runner=run)
    statuses = _collect_commit_statuses(actual_repo, head_sha, runner=run)
    required_checks = _resolve_required_checks(requirements, check_runs, statuses)
    _verify_pr_still_pinned(
        actual_repo,
        actual_number,
        head_sha=head_sha,
        base_ref=base_ref,
        changed_files_total=len(changed_files),
        runner=run,
    )
    ci_url = next(
        (check["details_url"] for check in required_checks if check["details_url"]),
        pr_url,
    )
    snapshot = {
        "schema_version": 1,
        "kind": "github_pr_ci_snapshot",
        "source": "github",
        "repo": actual_repo,
        "number": actual_number,
        "pr_url": pr_url,
        "state": state,
        "head_sha": head_sha,
        "base_ref": base_ref,
        "mergeable": mergeable,
        "changed_files": changed_files,
        "changed_files_total": len(changed_files),
        "changed_files_complete": True,
        "required_checks": required_checks,
        "declarations": {},
        "ci": {
            "head_sha": head_sha,
            "state": "success",
            "url": ci_url,
        },
    }
    validate_pr_ci_snapshot(snapshot)
    return snapshot


def validate_pr_ci_snapshot(snapshot: Mapping[str, Any]) -> None:
    """Validate the closed normalized PR/CI-snapshot schema."""

    value = _object(snapshot, field="PR snapshot")
    _exact_keys(value, PR_SNAPSHOT_KEYS, field="PR snapshot")
    if isinstance(value["schema_version"], bool) or value["schema_version"] != 1:
        raise EvidenceError("PR snapshot schema_version must be 1")
    if value["kind"] != "github_pr_ci_snapshot" or value["source"] != "github":
        raise EvidenceError("PR snapshot provenance is invalid")
    repo = _repo(value["repo"], field="PR snapshot repo")
    number = _positive_int(value["number"], field="PR snapshot number")
    expected_url = f"https://github.com/{repo}/pull/{number}"
    pr_url = _string(value["pr_url"], field="PR snapshot pr_url")
    if pr_url.casefold() != expected_url.casefold():
        raise EvidenceError("PR snapshot pr_url does not match repo and number")
    if value["state"] != "open":
        raise EvidenceError("PR snapshot state must be open")
    head_sha = _full_sha(value["head_sha"], field="PR snapshot head_sha")
    _string(value["base_ref"], field="PR snapshot base_ref")
    if value["mergeable"] is not True:
        raise EvidenceError("PR snapshot mergeable must be true")
    raw_files = _array(value["changed_files"], field="PR snapshot changed_files")
    files = [
        _safe_changed_path(path, field=f"PR snapshot changed_files[{index}]")
        for index, path in enumerate(raw_files)
    ]
    if files != sorted(set(files)):
        raise EvidenceError("PR snapshot changed_files must be sorted and unique")
    total = _non_negative_int(
        value["changed_files_total"],
        field="PR snapshot changed_files_total",
    )
    if total != len(files):
        raise EvidenceError("PR snapshot changed_files_total does not match changed_files")
    if value["changed_files_complete"] is not True:
        raise EvidenceError("PR snapshot changed_files_complete must be true")
    declarations = _object(value["declarations"], field="PR snapshot declarations")
    if declarations:
        raise EvidenceError("PR snapshot declarations must be empty")
    checks = _array(value["required_checks"], field="PR snapshot required_checks")
    if not checks:
        raise EvidenceError("PR snapshot required_checks must not be empty")
    check_order: list[tuple[str, int, str, int]] = []
    for index, raw_check in enumerate(checks):
        check = _object(raw_check, field=f"PR snapshot required_checks[{index}]")
        _exact_keys(
            check,
            REQUIRED_CHECK_KEYS,
            field=f"PR snapshot required_checks[{index}]",
        )
        name = _string(check["name"], field=f"PR snapshot required_checks[{index}].name")
        required_app_id = check["required_app_id"]
        if required_app_id is not None:
            required_app_id = _positive_int(
                required_app_id,
                field=f"PR snapshot required_checks[{index}].required_app_id",
            )
        source = check["source"]
        if source not in {"check_run", "commit_status"}:
            raise EvidenceError(f"PR snapshot required_checks[{index}].source is invalid")
        evidence_id = _positive_int(
            check["id"],
            field=f"PR snapshot required_checks[{index}].id",
        )
        app_id = check["app_id"]
        if app_id is not None:
            app_id = _positive_int(
                app_id,
                field=f"PR snapshot required_checks[{index}].app_id",
            )
        if source == "commit_status" and app_id is not None:
            raise EvidenceError("commit-status evidence cannot claim a GitHub App id")
        if required_app_id is not None and app_id != required_app_id:
            raise EvidenceError("required check evidence came from the wrong GitHub App")
        if check["head_sha"] != head_sha:
            raise EvidenceError("required check evidence is tied to a different head SHA")
        if check["status"] != "completed":
            raise EvidenceError("required check evidence is not completed")
        if source == "commit_status" and check["conclusion"] != "success":
            raise EvidenceError("commit-status evidence conclusion must be success")
        if source == "check_run" and check["conclusion"] not in PASSING_CONCLUSIONS:
            raise EvidenceError("required check evidence is not passing")
        _string(
            check["details_url"],
            field=f"PR snapshot required_checks[{index}].details_url",
            nonempty=False,
        )
        check_order.append(
            (
                name,
                -1 if required_app_id is None else required_app_id,
                source,
                evidence_id,
            )
        )
    if check_order != sorted(set(check_order)):
        raise EvidenceError("PR snapshot required_checks must be sorted and unique")
    ci = _object(value["ci"], field="PR snapshot ci")
    _exact_keys(ci, CI_KEYS, field="PR snapshot ci")
    if ci["head_sha"] != head_sha or ci["state"] != "success":
        raise EvidenceError("PR snapshot CI is not successful for its head SHA")
    _string(ci["url"], field="PR snapshot ci.url")


PR_MERGE_STATE_KEYS = {
    "schema_version",
    "kind",
    "source",
    "repo",
    "number",
    "pr_url",
    "state",
    "head_sha",
    "base_ref",
    "merged",
    "merge_sha",
}


def collect_pr_merge_state(
    repo: str,
    number: int,
    *,
    expected_head_sha: str,
    runner: Runner | None = None,
) -> dict[str, Any]:
    """Read the current merge state for one immutable PR head."""

    requested_repo = _repo(repo)
    requested_number = _positive_int(number, field="PR number")
    expected_head = _full_sha(expected_head_sha, field="expected head SHA")
    raw = _object(
        _api(
            "GET",
            f"repos/{requested_repo}/pulls/{requested_number}",
            runner=_runner_or_default(runner),
        ),
        field="GitHub PR merge-state response",
    )
    actual_number = _positive_int(raw.get("number"), field="GitHub PR number")
    if actual_number != requested_number:
        raise EvidenceError(
            f"GitHub PR number {actual_number} does not match requested PR {requested_number}"
        )
    base = _object(raw.get("base"), field="GitHub PR base")
    base_repo = _object(base.get("repo"), field="GitHub PR base.repo")
    actual_repo = _repo(base_repo.get("full_name"), field="GitHub PR base repo")
    _same_repo(requested_repo, actual_repo, field="GitHub PR repo")
    head = _object(raw.get("head"), field="GitHub PR head")
    head_sha = _full_sha(head.get("sha"), field="GitHub PR head SHA")
    if head_sha != expected_head:
        raise EvidenceError(
            f"PR head SHA {head_sha} does not match expected head SHA {expected_head}"
        )
    state = _string(raw.get("state"), field="GitHub PR state")
    if state not in {"open", "closed"}:
        raise EvidenceError(f"GitHub PR state is invalid: {state}")
    merged = raw.get("merged")
    if not isinstance(merged, bool):
        raise EvidenceError("GitHub PR merged must be a boolean")
    if merged and state != "closed":
        raise EvidenceError("a merged GitHub PR must be closed")
    merge_sha: str | None = None
    if merged:
        merge_sha = _full_sha(
            raw.get("merge_commit_sha"),
            field="GitHub PR merge commit SHA",
        )
    pr_url = _string(raw.get("html_url"), field="GitHub PR URL")
    expected_pr_url = f"https://github.com/{actual_repo}/pull/{actual_number}"
    if pr_url.casefold() != expected_pr_url.casefold():
        raise EvidenceError("GitHub PR URL does not match requested repo and PR number")
    snapshot = {
        "schema_version": 1,
        "kind": "github_pr_merge_state",
        "source": "github",
        "repo": actual_repo,
        "number": actual_number,
        "pr_url": pr_url,
        "state": state,
        "head_sha": head_sha,
        "base_ref": _string(base.get("ref"), field="GitHub PR base ref"),
        "merged": merged,
        "merge_sha": merge_sha,
    }
    validate_pr_merge_state(snapshot)
    return snapshot


def validate_pr_merge_state(snapshot: Mapping[str, Any]) -> None:
    """Validate the closed normalized PR merge-state schema."""

    value = _object(snapshot, field="PR merge-state snapshot")
    _exact_keys(value, PR_MERGE_STATE_KEYS, field="PR merge-state snapshot")
    if isinstance(value["schema_version"], bool) or value["schema_version"] != 1:
        raise EvidenceError("PR merge-state schema_version must be 1")
    if value["kind"] != "github_pr_merge_state" or value["source"] != "github":
        raise EvidenceError("PR merge-state provenance is invalid")
    repo = _repo(value["repo"], field="PR merge-state repo")
    number = _positive_int(value["number"], field="PR merge-state number")
    expected_url = f"https://github.com/{repo}/pull/{number}"
    if _string(value["pr_url"], field="PR merge-state pr_url").casefold() != (
        expected_url.casefold()
    ):
        raise EvidenceError("PR merge-state pr_url does not match repo and number")
    if value["state"] not in {"open", "closed"}:
        raise EvidenceError("PR merge-state state must be open or closed")
    _full_sha(value["head_sha"], field="PR merge-state head_sha")
    _string(value["base_ref"], field="PR merge-state base_ref")
    if not isinstance(value["merged"], bool):
        raise EvidenceError("PR merge-state merged must be a boolean")
    if value["merged"] is True:
        if value["state"] != "closed":
            raise EvidenceError("a merged PR merge-state must be closed")
        _full_sha(value["merge_sha"], field="PR merge-state merge_sha")
    elif value["merge_sha"] is not None:
        raise EvidenceError("an unmerged PR merge-state must have null merge_sha")


MERGE_RESPONSE_KEYS = {"sha", "merged", "message"}


def merge_pr(
    repo: str,
    number: int,
    *,
    expected_head_sha: str,
    merge_method: str = "squash",
    runner: Runner | None = None,
) -> dict[str, Any]:
    """Atomically merge a PR only if GitHub still reports the expected head SHA."""

    requested_repo = _repo(repo)
    requested_number = _positive_int(number, field="PR number")
    expected_head = _full_sha(expected_head_sha, field="expected head SHA")
    if merge_method not in {"merge", "squash", "rebase"}:
        raise EvidenceError("merge_method must be merge, squash, or rebase")
    raw = _object(
        _api(
            "PUT",
            f"repos/{requested_repo}/pulls/{requested_number}/merge",
            runner=_runner_or_default(runner),
            body={"merge_method": merge_method, "sha": expected_head},
        ),
        field="GitHub merge response",
    )
    _exact_keys(raw, MERGE_RESPONSE_KEYS, field="GitHub merge response")
    if raw["merged"] is not True:
        message = raw["message"] if isinstance(raw["message"], str) else "no message"
        raise EvidenceError(f"GitHub did not merge PR: {message}")
    try:
        merge_sha = _full_sha(raw["sha"], field="GitHub merge response sha")
    except EvidenceError as exc:
        raise EvidenceError("GitHub returned an invalid merge SHA") from exc
    message = _string(raw["message"], field="GitHub merge response message")
    return {
        "schema_version": 1,
        "kind": "github_pr_merge_result",
        "source": "github",
        "repo": requested_repo,
        "number": requested_number,
        "expected_head_sha": expected_head,
        "merge_method": merge_method,
        "merged": True,
        "merge_sha": merge_sha,
        "message": message,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Collect authoritative GitHub evidence or explicitly merge one PR.")
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    issue = subparsers.add_parser("collect-issue")
    issue.add_argument("--repo", required=True)
    issue.add_argument("--number", required=True, type=int)

    pr = subparsers.add_parser("collect-pr")
    pr.add_argument("--repo", required=True)
    pr.add_argument("--number", required=True, type=int)
    pr.add_argument("--expected-head-sha", required=True)

    merge_state = subparsers.add_parser("collect-merge-state")
    merge_state.add_argument("--repo", required=True)
    merge_state.add_argument("--number", required=True, type=int)
    merge_state.add_argument("--expected-head-sha", required=True)

    merge = subparsers.add_parser("merge-pr")
    merge.add_argument("--repo", required=True)
    merge.add_argument("--number", required=True, type=int)
    merge.add_argument("--expected-head-sha", required=True)
    merge.add_argument(
        "--merge-method",
        choices=("merge", "squash", "rebase"),
        default="squash",
    )
    return parser


def main(argv: Sequence[str] | None = None, *, runner: Runner | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "collect-issue":
            result = collect_issue(args.repo, args.number, runner=runner)
        elif args.command == "collect-pr":
            result = collect_pr_ci(
                args.repo,
                args.number,
                expected_head_sha=args.expected_head_sha,
                runner=runner,
            )
        elif args.command == "collect-merge-state":
            result = collect_pr_merge_state(
                args.repo,
                args.number,
                expected_head_sha=args.expected_head_sha,
                runner=runner,
            )
        elif args.command == "merge-pr":
            result = merge_pr(
                args.repo,
                args.number,
                expected_head_sha=args.expected_head_sha,
                merge_method=args.merge_method,
                runner=runner,
            )
        else:
            raise AssertionError(f"unhandled command: {args.command}")
    except EvidenceError as exc:
        print(
            json.dumps(
                {"error": str(exc), "type": type(exc).__name__},
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
