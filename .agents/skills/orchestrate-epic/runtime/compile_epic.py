#!/usr/bin/env python3
"""Compile a normalized epic specification into an immutable epicctl manifest.

This is the generic entry point for new epics. Repository-specific adapters may
still collect live issue evidence, but they must lower into this schema instead
of teaching the control plane another epic's prose.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, NoReturn

import yamlrocks

YAML_OPTIONS = yamlrocks.OPT_DUPLICATE_KEYS_ERROR | yamlrocks.OPT_REJECT_COMPLEX_KEYS
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")


class SpecError(ValueError):
    """One user-facing normalized-epic diagnostic."""


def _fail(message: str) -> NoReturn:
    raise SpecError(message)


def _load(path: Path) -> dict[str, Any]:
    try:
        if path.suffix.lower() == ".json":
            value = json.loads(path.read_text())
        else:
            value = yamlrocks.loads(path.read_bytes(), option=YAML_OPTIONS)
    except (OSError, json.JSONDecodeError, yamlrocks.YAMLRocksError) as exc:
        _fail(f"cannot read epic spec {path}: {exc}")
    if not isinstance(value, dict):
        _fail("epic spec must be an object")
    return value


def _closed(value: dict[str, Any], allowed: set[str], *, at: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        _fail(f"{at} contains unknown fields: {', '.join(unknown)}")


def _text(value: Any, *, at: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{at} must be a non-empty string")
    return value.strip()


def _strings(value: Any, *, at: str, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        _fail(f"{at} must be an array of non-empty strings")
    if nonempty and not value:
        _fail(f"{at} must not be empty")
    if len(value) != len(set(value)):
        _fail(f"{at} must not contain duplicates")
    return [item.strip() for item in value]


def _positive(value: Any, *, at: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _fail(f"{at} must be a positive integer")
    return value


def _identity(value: Any, *, at: str) -> dict[str, str]:
    if not isinstance(value, dict):
        _fail(f"{at} must be an object")
    _closed(value, {"family", "model", "effort"}, at=at)
    result = {
        "family": _text(value.get("family"), at=f"{at}.family"),
        "model": _text(value.get("model"), at=f"{at}.model"),
    }
    effort = value.get("effort")
    if effort is not None:
        result["effort"] = _text(effort, at=f"{at}.effort")
    return result


def _profiles(value: Any, *, at: str) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict) or not value:
        _fail(f"{at} must be a non-empty object")
    return {
        _text(name, at=f"{at} key"): _identity(identity, at=f"{at}.{name}")
        for name, identity in value.items()
    }


def _validate_goal_tree(value: Any, tasks: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("goal_tree must be an object")
    leaves: list[str] = []
    ids: set[str] = set()

    def visit(node: Any, depth: int) -> None:
        if depth > 8:
            _fail("goal_tree depth must not exceed 8")
        if not isinstance(node, dict):
            _fail("goal_tree children must be objects")
        node_id = _text(node.get("id"), at="goal_tree.id")
        if node_id in ids:
            _fail(f"goal_tree id appears more than once: {node_id}")
        ids.add(node_id)
        if "task" in node:
            _closed(node, {"id", "task"}, at=f"goal_tree leaf {node_id}")
            leaves.append(_text(node["task"], at=f"goal_tree leaf {node_id}.task"))
            return
        _closed(node, {"id", "goal", "children"}, at=f"goal_tree branch {node_id}")
        _text(node.get("goal"), at=f"goal_tree branch {node_id}.goal")
        children = node.get("children")
        if not isinstance(children, list) or not children:
            _fail(f"goal_tree branch {node_id}.children must be non-empty")
        for child in children:
            visit(child, depth + 1)

    visit(value, 0)
    if len(leaves) != len(set(leaves)):
        _fail("goal_tree references one task more than once")
    leaf_set = set(leaves)
    if leaf_set != tasks:
        _fail(
            "goal_tree leaves must cover tasks exactly; "
            f"missing={sorted(tasks - leaf_set)}, unexpected={sorted(leaf_set - tasks)}"
        )
    return deepcopy(value)


def _model_policy(value: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(value, dict):
        _fail("models must be an object")
    _closed(value, {"planners", "workers", "reviewers", "routing"}, at="models")
    planners = _profiles(value.get("planners"), at="models.planners")
    workers = _profiles(value.get("workers"), at="models.workers")
    reviewers = _profiles(value.get("reviewers"), at="models.reviewers")
    routing = value.get("routing")
    if not isinstance(routing, dict):
        _fail("models.routing must be an object")
    _closed(
        routing,
        {
            "planner_primary",
            "planner_escalation",
            "worker_default",
            "worker_by_risk",
            "reviewer_by_worker",
        },
        at="models.routing",
    )
    planner_primary = _text(routing.get("planner_primary"), at="models.routing.planner_primary")
    planner_escalation = _text(
        routing.get("planner_escalation"), at="models.routing.planner_escalation"
    )
    worker_default = _text(routing.get("worker_default"), at="models.routing.worker_default")
    for name, profiles, at in (
        (planner_primary, planners, "planner_primary"),
        (planner_escalation, planners, "planner_escalation"),
        (worker_default, workers, "worker_default"),
    ):
        if name not in profiles:
            _fail(f"models.routing.{at} names unknown profile {name!r}")
    worker_by_risk = routing.get("worker_by_risk", {})
    if not isinstance(worker_by_risk, dict):
        _fail("models.routing.worker_by_risk must be an object")
    _closed(worker_by_risk, {"mechanical", "novel"}, at="models.routing.worker_by_risk")
    normalized_worker_by_risk: dict[str, str] = {}
    for risk in ("mechanical", "novel"):
        profile = worker_by_risk.get(risk, worker_default)
        profile = _text(profile, at=f"models.routing.worker_by_risk.{risk}")
        if profile not in workers:
            _fail(f"worker risk route names unknown profile {profile!r}")
        normalized_worker_by_risk[risk] = profile
    reviewer_by_worker = routing.get("reviewer_by_worker")
    if not isinstance(reviewer_by_worker, dict):
        _fail("models.routing.reviewer_by_worker must be an object")
    if set(reviewer_by_worker) != set(workers):
        _fail("reviewer_by_worker must cover every worker profile exactly")
    normalized_reviewers: dict[str, str] = {}
    for worker_name, reviewer_name_raw in reviewer_by_worker.items():
        reviewer_name = _text(
            reviewer_name_raw, at=f"models.routing.reviewer_by_worker.{worker_name}"
        )
        if reviewer_name not in reviewers:
            _fail(f"reviewer route names unknown profile {reviewer_name!r}")
        if workers[worker_name]["family"] == reviewers[reviewer_name]["family"]:
            _fail(
                f"worker {worker_name!r} and reviewer {reviewer_name!r} must use different families"
            )
        normalized_reviewers[worker_name] = reviewer_name

    default_reviewer = normalized_reviewers[worker_default]
    current = {
        "planner": deepcopy(planners[planner_primary]),
        "worker": deepcopy(workers[worker_default]),
        "reviewer": deepcopy(reviewers[default_reviewer]),
    }
    extended = {
        "model_profiles": {
            "planners": planners,
            "workers": workers,
            "reviewers": reviewers,
        },
        "model_routing": {
            "planner_primary": planner_primary,
            "planner_escalation": planner_escalation,
            "worker_default": worker_default,
            "worker_by_risk": normalized_worker_by_risk,
            "reviewer_by_worker": normalized_reviewers,
        },
    }
    return current, extended


def _checks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        _fail("checks must be a non-empty array")
    names: set[str] = set()
    result: list[dict[str, Any]] = []
    for index, check in enumerate(value):
        if not isinstance(check, dict):
            _fail(f"checks[{index}] must be an object")
        _closed(check, {"name", "command"}, at=f"checks[{index}]")
        name = _text(check.get("name"), at=f"checks[{index}].name")
        if name in names:
            _fail(f"duplicate check name {name!r}")
        command = _strings(check.get("command"), at=f"checks[{index}].command", nonempty=True)
        names.add(name)
        result.append({"name": name, "command": command})
    return result


def _task(
    task_id: str,
    value: Any,
    *,
    check_names: set[str],
    model_profiles: dict[str, Any],
    routing: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"tasks.{task_id} must be an object")
    _closed(
        value,
        {
            "repo",
            "issue",
            "depends_on",
            "risk",
            "lane",
            "forbidden_paths",
            "acceptance_criteria",
            "required_checks",
            "done_artifacts",
            "outcome",
            "decision_boundary",
            "interfaces",
            "uncertainty",
            "worker_profile",
            "reviewer_profile",
            "initial",
        },
        at=f"tasks.{task_id}",
    )
    risk = value.get("risk")
    if risk not in {"mechanical", "novel"}:
        _fail(f"tasks.{task_id}.risk must be mechanical or novel")
    uncertainty = value.get("uncertainty", "medium")
    if uncertainty not in {"low", "medium", "high"}:
        _fail(f"tasks.{task_id}.uncertainty must be low, medium, or high")
    worker_profile = value.get("worker_profile", routing["worker_by_risk"][risk])
    worker_profile = _text(worker_profile, at=f"tasks.{task_id}.worker_profile")
    workers = model_profiles["workers"]
    reviewers = model_profiles["reviewers"]
    if worker_profile not in workers:
        _fail(f"tasks.{task_id} names unknown worker profile {worker_profile!r}")
    reviewer_profile = value.get(
        "reviewer_profile", routing["reviewer_by_worker"][worker_profile]
    )
    reviewer_profile = _text(reviewer_profile, at=f"tasks.{task_id}.reviewer_profile")
    if reviewer_profile not in reviewers:
        _fail(f"tasks.{task_id} names unknown reviewer profile {reviewer_profile!r}")
    if workers[worker_profile]["family"] == reviewers[reviewer_profile]["family"]:
        _fail(f"tasks.{task_id} worker and reviewer families must differ")
    required = _strings(
        value.get("required_checks"), at=f"tasks.{task_id}.required_checks", nonempty=True
    )
    unknown_checks = sorted(set(required) - check_names)
    if unknown_checks:
        _fail(f"tasks.{task_id} names unknown checks: {', '.join(unknown_checks)}")
    result: dict[str, Any] = {
        "repo": _text(value.get("repo"), at=f"tasks.{task_id}.repo"),
        "depends_on": _strings(value.get("depends_on", []), at=f"tasks.{task_id}.depends_on"),
        "risk": risk,
        "lane": _strings(value.get("lane"), at=f"tasks.{task_id}.lane", nonempty=True),
        "acceptance_criteria": _strings(
            value.get("acceptance_criteria"),
            at=f"tasks.{task_id}.acceptance_criteria",
            nonempty=True,
        ),
        "required_checks": required,
        "forbidden_paths": _strings(
            value.get("forbidden_paths", []), at=f"tasks.{task_id}.forbidden_paths"
        ),
        "done_artifacts": _strings(
            value.get("done_artifacts", []), at=f"tasks.{task_id}.done_artifacts"
        ),
        "outcome": _text(value.get("outcome"), at=f"tasks.{task_id}.outcome"),
        "decision_boundary": _text(
            value.get("decision_boundary", "Do not change an ancestor or sibling contract."),
            at=f"tasks.{task_id}.decision_boundary",
        ),
        "interfaces": _strings(value.get("interfaces", []), at=f"tasks.{task_id}.interfaces"),
        "uncertainty": uncertainty,
        "worker_profile": worker_profile,
        "reviewer_profile": reviewer_profile,
    }
    if "issue" in value:
        result["source"] = {"issue": _text(value["issue"], at=f"tasks.{task_id}.issue")}
    if "initial" in value:
        initial = value["initial"]
        if not isinstance(initial, dict):
            _fail(f"tasks.{task_id}.initial must be an object")
        result["initial"] = deepcopy(initial)
    return result


def compile_spec(spec: dict[str, Any]) -> dict[str, Any]:
    _closed(
        spec,
        {
            "schema_version",
            "run",
            "epic",
            "models",
            "checks",
            "protected_paths",
            "no_go_paths",
            "barriers",
            "goal_tree",
            "tasks",
        },
        at="epic spec",
    )
    if spec.get("schema_version") != 1:
        _fail("schema_version must be 1")
    run = spec.get("run")
    if not isinstance(run, dict):
        _fail("run must be an object")
    _closed(
        run,
        {
            "id",
            "epoch",
            "predecessor_manifest_digest",
            "source_main_sha",
            "base_ref",
            "max_concurrent",
            "max_same_finding_rejections",
            "max_review_rejections",
            "require_ci",
        },
        at="run",
    )
    epic = spec.get("epic")
    if not isinstance(epic, dict):
        _fail("epic must be an object")
    _closed(epic, {"id", "outcome", "non_goals", "success_metrics"}, at="epic")
    epic_id = _text(epic.get("id"), at="epic.id")
    run_id = _text(run.get("id"), at="run.id")
    epoch = _positive(run.get("epoch", 1), at="run.epoch")
    predecessor = run.get("predecessor_manifest_digest")
    if epoch == 1:
        if predecessor is not None:
            _fail("run.predecessor_manifest_digest must be null for epoch 1")
    elif not isinstance(predecessor, str) or SHA64.fullmatch(predecessor) is None:
        _fail("successor epoch needs a lowercase 64-hex predecessor_manifest_digest")
    source_main_sha = _text(run.get("source_main_sha"), at="run.source_main_sha")
    if SHA40.fullmatch(source_main_sha) is None:
        _fail("run.source_main_sha must be a lowercase full Git SHA")
    current_models, extended_models = _model_policy(spec.get("models"))
    checks = _checks(spec.get("checks"))
    check_names = {check["name"] for check in checks}
    tasks_raw = spec.get("tasks")
    if not isinstance(tasks_raw, dict) or not tasks_raw:
        _fail("tasks must be a non-empty object")
    task_ids = {_text(task, at="task id") for task in tasks_raw}
    profiles = extended_models["model_profiles"]
    routing = extended_models["model_routing"]
    tasks = {
        task_id: _task(
            task_id,
            tasks_raw[task_id],
            check_names=check_names,
            model_profiles=profiles,
            routing=routing,
        )
        for task_id in sorted(task_ids)
    }
    for task_id, definition in tasks.items():
        unknown = sorted(set(definition["depends_on"]) - task_ids)
        if unknown:
            _fail(f"tasks.{task_id} depends on unknown tasks: {', '.join(unknown)}")
    goal_tree = _validate_goal_tree(spec.get("goal_tree"), task_ids)
    barriers = spec.get("barriers", [])
    if not isinstance(barriers, list):
        _fail("barriers must be an array")
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "epic": epic_id,
        "epoch": epoch,
        "predecessor_manifest_digest": predecessor,
        "source_main_sha": source_main_sha,
        "base_ref": _text(run.get("base_ref", "main"), at="run.base_ref"),
        "max_concurrent": _positive(run.get("max_concurrent", 2), at="run.max_concurrent"),
        "max_same_finding_rejections": _positive(
            run.get("max_same_finding_rejections", 2),
            at="run.max_same_finding_rejections",
        ),
        "max_review_rejections": _positive(
            run.get("max_review_rejections", 4), at="run.max_review_rejections"
        ),
        "require_ci": run.get("require_ci", True),
        "models": current_models,
        **extended_models,
        "checks": checks,
        "protected_paths": _strings(spec.get("protected_paths", []), at="protected_paths"),
        "no_go_paths": _strings(spec.get("no_go_paths", []), at="no_go_paths"),
        "barriers": deepcopy(barriers),
        "goal_tree": goal_tree,
        "tasks": tasks,
        "epic_contract": {
            "outcome": _text(epic.get("outcome"), at="epic.outcome"),
            "non_goals": _strings(epic.get("non_goals", []), at="epic.non_goals"),
            "success_metrics": _strings(epic.get("success_metrics", []), at="epic.success_metrics"),
        },
    }
    if not isinstance(manifest["require_ci"], bool):
        _fail("run.require_ci must be a boolean")
    return manifest


def _digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = compile_spec(_load(args.spec))
    except SpecError as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    result = {
        "manifest": str(args.output),
        "manifest_digest": _digest(manifest),
        "tasks": len(manifest["tasks"]),
    }
    if args.summary:
        result["routing"] = manifest["model_routing"]
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
