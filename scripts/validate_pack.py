#!/usr/bin/env python3
"""End-to-end validation of the Copier template pack.

The loop:

1. verify template/ contains no local runtime artifacts;
2. instantiate a throwaway repository inside a temporary directory;
3. verify no unrendered Jinja survives in file names or contents;
4. initialize Git, then bootstrap dependencies, prek hooks, and checks;
5. seed deterministic repair probes and verify bootstrap repairs them;
6. delete both prek shims and prove the generated gate repairs them;
7. commit the baseline and prove a tracked, un-imported syntax error fails early;
8. prove linked worktrees share both prek hooks;
9. delete the throwaway repository.

Every failure message states what broke and how to fix it, so both humans
and coding agents can act on it without re-deriving the intent.
"""

import fnmatch
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = REPO_ROOT / "template"
COPIER_CONFIG = REPO_ROOT / "copier.yml"
PROJECT_NAME = "orchard-billing"
PACKAGE_NAME = "orchard_billing"


def artifact_exclusion_patterns() -> tuple[str, ...]:
    """Read artifact exclusions from copier.yml, their single source of truth."""
    patterns: list[str] = []
    in_exclude = False
    for raw_line in COPIER_CONFIG.read_text(encoding="utf-8").splitlines():
        if raw_line == "_exclude:":
            in_exclude = True
            continue
        if in_exclude and raw_line.startswith("  - "):
            patterns.append(raw_line.removeprefix("  - ").strip('"\''))
            continue
        if in_exclude and raw_line and not raw_line.startswith(" "):
            break
    if not patterns:
        raise ValueError("copier.yml must define a non-empty _exclude list")
    return tuple(patterns)


def find_forbidden_artifacts(root: Path) -> list[Path]:
    """Return every entry under *root* matching an ignored artifact pattern."""
    patterns = artifact_exclusion_patterns()
    return sorted(
        path
        for path in root.rglob("*")
        if any(fnmatch.fnmatch(path.name, pattern) for pattern in patterns)
    )


def find_unrendered_jinja(root: Path) -> list[str]:
    """Return human-readable locations where template syntax survives rendering."""
    occurrences: list[str] = []
    jinja_syntax = re.compile(
        r"(?<![$\{])\{\{[-+]?\s*[A-Za-z_]|\{%[-+]?\s*[A-Za-z_]|\{#[-+]?"
    )
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.name.endswith(".jinja"):
            occurrences.append(f"{relative}: stray .jinja template suffix")
        if jinja_syntax.search(relative.as_posix()):
            occurrences.append(f"{relative}: Jinja syntax in file or directory name")
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if jinja_syntax.search(line):
                occurrences.append(f"{relative}:{line_number}: contains Jinja syntax")
    return occurrences


def seed_repair_probes(root: Path) -> dict[Path, str]:
    """Introduce lint/format and diagram drift for the downstream loop to repair."""
    entry_point = root / "src" / PACKAGE_NAME / "__main__.py"
    model = root / "docs" / "architecture" / "likec4" / "generated" / "model.c4"
    expected: dict[Path, str] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            expected[path] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    broken_entry_point = expected[entry_point].replace(
        'if __name__ == "__main__":', 'if  __name__=="__main__":'
    )
    if broken_entry_point == expected[entry_point]:
        raise ValueError("repair probe could not find the generated __main__ guard")
    _ = entry_point.write_text(broken_entry_point, encoding="utf-8")
    _ = model.write_text(f"{expected[model]}\n", encoding="utf-8")
    return expected


def fail(step: str, details: list[str], fix: str) -> int:
    print(f"\nVALIDATION FAILED at step: {step}", file=sys.stderr)
    for detail in details:
        print(f"  {detail}", file=sys.stderr)
    print(f"FIX: {fix}", file=sys.stderr)
    return 1


def run_step(
    name: str, command: list[str], cwd: Path, *, input_text: str | None = None
) -> int:
    print(f"\n=== {name} ===", flush=True)
    print(f"$ {' '.join(command)}  (cwd={cwd})", flush=True)
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PYTHONPATH"}
    }
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        input=input_text,
        text=input_text is not None,
        check=False,
    )
    return completed.returncode


def run_captured_step(
    name: str, command: list[str], cwd: Path
) -> subprocess.CompletedProcess[str]:
    print(f"\n=== {name} ===", flush=True)
    print(f"$ {' '.join(command)}  (cwd={cwd})", flush=True)
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PYTHONPATH"}
    }
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    print(completed.stdout, end="")
    print(completed.stderr, end="", file=sys.stderr)
    return completed


def effective_git_path(root: Path, path: str) -> Path | None:
    """Return Git's absolute effective path, or None when Git cannot resolve it."""
    completed = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-path", path],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return Path(completed.stdout.strip())


def worktree_hook_errors(primary: Path, linked: Path) -> list[str]:
    """Return defects in prek shim sharing between primary and linked worktrees."""
    errors: list[str] = []
    for hook in ("pre-commit", "pre-push"):
        primary_hook = effective_git_path(primary, f"hooks/{hook}")
        linked_hook = effective_git_path(linked, f"hooks/{hook}")
        if primary_hook is None or linked_hook is None:
            errors.append(f"Git could not resolve the effective {hook} hook path.")
            continue
        if linked_hook != primary_hook:
            errors.append(
                f"{hook} is not shared: primary={primary_hook}, linked={linked_hook}"
            )
        if not primary_hook.is_file() or not os.access(primary_hook, os.X_OK):
            errors.append(f"{primary_hook} is not an executable prek shim.")
    return errors


def main() -> int:
    print("=== template cleanliness ===")
    artifacts = find_forbidden_artifacts(TEMPLATE_ROOT)
    if artifacts:
        return fail(
            "template cleanliness",
            [str(path.relative_to(REPO_ROOT)) for path in artifacts],
            "Delete these local artifacts from template/. The forbidden patterns are "
            "the _exclude entries in copier.yml.",
        )
    print("template/ contains no local runtime artifacts.")

    for tool in ("git", "just", "uv"):
        if shutil.which(tool) is None:
            return fail(
                "toolchain",
                [f"'{tool}' was not found on PATH."],
                "Install the prerequisites listed in AGENTS.md before running pack validation.",
            )

    with tempfile.TemporaryDirectory(prefix="guardrails-pack-validate-") as scratch:
        target = Path(scratch) / PROJECT_NAME

        exit_code = run_step(
            "instantiate throwaway repository",
            [sys.executable, str(REPO_ROOT / "instantiate.py"), PROJECT_NAME, PACKAGE_NAME, str(target)],
            REPO_ROOT,
        )
        if exit_code != 0:
            return fail(
                "instantiate",
                [f"instantiate.py exited with {exit_code}."],
                "Read the generator output above; fix instantiate.py or template/.",
            )

        print("\n=== unrendered Jinja scan ===")
        leftovers = find_unrendered_jinja(target)
        if leftovers:
            return fail(
                "unrendered Jinja scan",
                leftovers,
                "Every rendered template file and path must use the .jinja suffix; check "
                "copier.yml and the canonical source under template/.",
            )
        print("No unrendered Jinja survives in the generated repository.")

        exit_code = run_step(
            "initialize throwaway Git repository",
            ["git", "init", "--quiet", "--initial-branch=main"],
            target,
        )
        if exit_code != 0:
            return fail(
                "Git initialization",
                [f"'git init --quiet --initial-branch=main' exited with {exit_code}."],
                "Check the local Git installation; generated repositories must initialize "
                "before bootstrap installs hooks.",
            )

        expected_after_repairs = seed_repair_probes(target)
        exit_code = run_step("bootstrap generated repository", ["just", "bootstrap"], target)
        if exit_code != 0:
            return fail(
                "downstream bootstrap",
                [f"'just bootstrap' exited with {exit_code}."],
                "The generated repository must resolve dependencies, install prek hooks, and "
                "pass its own check loop. Fix the canonical source under template/ and re-run "
                "'just validate'.",
            )
        stale_probes = [
            str(path.relative_to(target))
            for path, expected in expected_after_repairs.items()
            if path.read_text(encoding="utf-8") != expected
        ]
        if stale_probes:
            return fail(
                "downstream repair probes",
                stale_probes,
                "Make 'just check' apply deterministic Ruff and diagram repairs before its gate.",
            )

        print("\n=== missing-hook repair probe ===")
        for hook in ("pre-commit", "pre-push"):
            hook_path = effective_git_path(target, f"hooks/{hook}")
            if hook_path is None:
                return fail(
                    "missing-hook repair probe",
                    [f"Git could not resolve the effective {hook} hook path."],
                    "The generated gate must inspect Git's shared hooks directory.",
                )
            hook_path.unlink(missing_ok=True)
        exit_code = run_step(
            "repair missing hooks through generated gate", ["just", "check"], target
        )
        if exit_code != 0:
            return fail(
                "missing-hook repair probe",
                [f"'just check' exited with {exit_code} after both shims were deleted."],
                "Make the gate run 'uv run prek install -f' before every other check when "
                "the shared prek shims are absent.",
            )
        hook_errors = worktree_hook_errors(target, target)
        if hook_errors:
            return fail(
                "missing-hook repair probe",
                hook_errors,
                "The generated gate must leave executable pre-commit and pre-push prek shims "
                "in Git's shared hooks directory.",
            )

        for name, command in (
            ("stage bootstrapped baseline", ["git", "add", "--all"]),
            (
                "commit bootstrapped baseline",
                [
                    "git",
                    "-c",
                    "user.name=pack-validation",
                    "-c",
                    "user.email=pack-validation@localhost",
                    "commit",
                    "--quiet",
                    "--message=validated baseline",
                ],
            ),
        ):
            exit_code = run_step(name, command, target)
            if exit_code != 0:
                return fail(
                    name,
                    [f"'{' '.join(command)}' exited with {exit_code}."],
                    "The bootstrapped baseline must pass its installed pre-commit hooks.",
                )

        syntax_probe = target / "unimported_syntax_error.py"
        syntax_probe.write_text("def unseen(:\n    pass\n", encoding="utf-8")
        exit_code = run_step(
            "stage tracked syntax probe", ["git", "add", syntax_probe.name], target
        )
        if exit_code != 0:
            return fail(
                "tracked Python syntax probe",
                [f"'git add {syntax_probe.name}' exited with {exit_code}."],
                "The planted un-imported Python file must be tracked before probing the gate.",
            )
        syntax_gate = run_captured_step(
            "reject tracked un-imported syntax error", ["just", "check"], target
        )
        if syntax_gate.returncode == 0 or "FAILED: tracked Python syntax" not in (
            syntax_gate.stdout + syntax_gate.stderr
        ):
            return fail(
                "tracked Python syntax probe",
                [
                    f"'just check' exited with {syntax_gate.returncode}; expected the tracked "
                    "Python syntax step to fail."
                ],
                "Parse every tracked '*.py' file before repairs and the remaining quality gate.",
            )
        exit_code = run_step(
            "unstage tracked syntax probe",
            ["git", "restore", "--staged", syntax_probe.name],
            target,
        )
        if exit_code != 0:
            return fail(
                "tracked Python syntax probe cleanup",
                [f"'git restore --staged {syntax_probe.name}' exited with {exit_code}."],
                "Remove the temporary syntax probe from the generated repository index.",
            )
        syntax_probe.unlink()

        linked = Path(scratch) / "linked-worktree"
        exit_code = run_step(
            "create linked worktree",
            ["git", "worktree", "add", "--quiet", "--detach", str(linked)],
            target,
        )
        if exit_code != 0:
            return fail(
                "linked worktree creation",
                [f"'git worktree add' exited with {exit_code}."],
                "The committed generated repository must support a standard linked worktree.",
            )
        hook_errors = worktree_hook_errors(target, linked)
        if hook_errors:
            return fail(
                "linked worktree prek hooks",
                hook_errors,
                "Install prek before the initial commit so Git's shared hooks directory covers "
                "the primary repository and every linked worktree.",
            )
        probe = linked / "worktree-hook-probe.txt"
        probe.write_text("probe\n", encoding="utf-8")
        exit_code = run_step(
            "stage linked hook probe", ["git", "add", probe.name], linked
        )
        if exit_code != 0:
            return fail(
                "linked worktree prek hook execution",
                [f"'git add {probe.name}' exited with {exit_code}."],
                "Stage a clean linked-worktree file before invoking the pre-commit shim.",
            )
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=linked,
            capture_output=True,
            text=True,
            check=False,
        )
        if head.returncode != 0:
            return fail(
                "linked worktree prek hook execution",
                ["Git could not resolve the linked worktree HEAD."],
                "The linked worktree must have a committed baseline before hook probes.",
            )
        push_update = (
            f"refs/heads/main {head.stdout.strip()} refs/heads/main {'0' * 40}\n"
        )
        for hook in ("pre-commit", "pre-push"):
            hook_path = effective_git_path(linked, f"hooks/{hook}")
            if hook_path is None:
                return fail(
                    "linked worktree prek hook execution",
                    [f"Git could not resolve the linked {hook} hook path."],
                    "Resolve and execute each installed shim from the linked worktree.",
                )
            arguments = [str(hook_path)]
            if hook == "pre-push":
                arguments.extend(("origin", "unused"))
            exit_code = run_step(
                f"run linked {hook} hook",
                arguments,
                linked,
                input_text=push_update if hook == "pre-push" else None,
            )
            if exit_code != 0:
                return fail(
                    "linked worktree prek hook execution",
                    [f"The linked {hook} shim exited with {exit_code}."],
                    "Both shared prek shims must execute successfully from a linked worktree.",
                )
        exit_code = run_step(
            "remove linked worktree",
            ["git", "worktree", "remove", "--force", str(linked)],
            target,
        )
        if exit_code != 0:
            return fail(
                "linked worktree cleanup",
                [f"'git worktree remove --force' exited with {exit_code}."],
                "Validation worktrees must be removed through Git before temporary cleanup.",
            )

    print("\nPack validation passed: template is clean, instantiation is fully rendered,")
    print("bootstrap repairs drift; the gate repairs prek hooks, parses tracked Python,")
    print("and runs the shared shims from linked worktrees.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
