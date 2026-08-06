"""Build a pack, install it as a tool, and synthesise the previous release.

Rule `H1` admits one seam only: the console script of a throwaway tool
installation of a freshly built wheel. Every function here exists to reach that
seam, and none of them states an assertion.

`previous_release` builds the pack the `OLD` fixture is born from. The new wheel
must carry one real `ADD`, one real `REPLACE` and one real `DELETE` on the
Pack-owned Surface, so the previous tree is the current tree with the three
inverse changes and a lower version. Its manifest is then rewritten by the
previous tree's own `manifest` script, so the fixture records itself and no
record comes from the code the update tests measure.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys
import tarfile
from typing import cast

from guardrails_pack.bootstrap.tests.acceptance.code import CAPABILITY, Tokens, pack_tokens
from guardrails_pack.bootstrap.tests.acceptance.harness import (
    Outcome,
    make_repository,
    run,
)

__all__ = [
    "ADDED_BY_NEW",
    "DELETED_BY_NEW",
    "PAYLOAD",
    "POLICY_PROBE",
    "PREVIOUS_VERSION",
    "REPLACED_BY_NEW",
    "Pack",
    "build_wheel",
    "extract_commit",
    "install_tool",
    "previous_release",
    "staged_payload",
    "write_manifest",
]

PAYLOAD = "_pack.tar"
SOURCE_DIRECTORY = "src"
CAPABILITY_DIRECTORY = CAPABILITY
STARTING_FILES = "initial"
UNSHADOWED_FILE = "NOTES.md"
SCRIPT_NAME = "pyrepo"
MANIFEST_MODULE = "scripts.manifest_guard"
PACK_ON_PATH = "pack"
PROJECT_FILE = "pyproject.toml"
PREVIOUS_VERSION = "0.0.1"
# The three pack-owned differences that make the current wheel a real release
# against the previous one. `ADDED_BY_NEW` is absent from the previous tree,
# `DELETED_BY_NEW` is present only there, and `REPLACED_BY_NEW` differs.
ADDED_BY_NEW = "pack/docs/architecture/PATTERN_ADMISSION.md"
DELETED_BY_NEW = "pack/configs/retired.toml"
REPLACED_BY_NEW = "pack/configs/pytest.ini"
REPLACEMENT_LINE = "# The previous release of this policy.\n"
# The one policy the previous release loosens: it excludes one file name from
# every Ruff rule, and the current release checks it. Assertion `UPD-12` writes
# a user file of that name, so an update carries real policy onto real user
# code. Loosening a global setting instead reformats the pack itself.
POLICY_FILE = "pack/configs/ruff.toml"
POLICY_EXCLUSIONS = 'extend-exclude = ["../../.agents"]'
LOOSE_EXCLUSIONS = 'extend-exclude = ["../../.agents", "wide_probe.py"]'
POLICY_PROBE = "wide_probe.py"
RETIRED_POLICY = "# A policy file that the next release deletes.\n"
MANIFEST_PATH = "pack/manifest.json"
# The user-owned path that the record of `claiming_release` names. It exists in
# every project, and every update must leave it untouched.
CLAIMED_PATH = "README.md"


@dataclass(frozen=True, slots=True)
class Pack:
    """One built and installed pack: its tree, its wheel, and its console script."""

    root: Path
    wheel: Path
    script: Path
    tokens: Tokens


def staged_payload(root: Path, tokens: Tokens) -> Path:
    """Where a build stages the projection payload inside the package."""
    return root / SOURCE_DIRECTORY / tokens.package / PAYLOAD


def build_wheel(root: Path, distribution: Path) -> Path:
    """Stage the payload, build one wheel of *root*, then delete the payload."""
    tokens = pack_tokens(root)
    payload = staged_payload(root, tokens)
    try:
        archive = run(("git", "archive", "HEAD", "-o", str(payload)), root)
        assert archive.code == 0, archive.text
        built = run(("uv", "build", "--wheel", "-o", str(distribution)), root)
        assert built.code == 0, built.text
    finally:
        payload.unlink(missing_ok=True)
    wheels = sorted(distribution.glob("*.whl"))
    assert len(wheels) == 1, wheels
    return wheels[0]


def install_tool(wheel: Path, work: Path, name: str) -> Path:
    """Install *wheel* into a throwaway tool location and return its script."""
    tools, binaries = work / f"tools-{name}", work / f"bin-{name}"
    installed = run(
        ("uv", "tool", "install", "--force", str(wheel)),
        work,
        UV_TOOL_DIR=str(tools),
        UV_TOOL_BIN_DIR=str(binaries),
    )
    assert installed.code == 0, installed.text
    script = binaries / SCRIPT_NAME
    assert script.is_file(), sorted(binaries.iterdir())
    return script


def extract_commit(root: Path, destination: Path) -> Path:
    """Write the tree of `HEAD` of *root* into *destination*."""
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination.parent / f"{destination.name}.tar"
    made = run(("git", "archive", "HEAD", "-o", str(archive)), root)
    assert made.code == 0, made.text
    with tarfile.open(archive) as opened:
        opened.extractall(destination, filter="data")
    archive.unlink()
    return destination


def write_manifest(tree: Path) -> Outcome:
    """Record the pack-owned bytes of *tree* with that tree's own script."""
    return run(
        (sys.executable, "-m", MANIFEST_MODULE, "--write"),
        tree,
        PYTHONPATH=str(tree / PACK_ON_PATH),
    )


def _lower_the_version(tree: Path) -> None:
    project = tree / PROJECT_FILE
    text = project.read_text(encoding="utf-8")
    tokens = pack_tokens(tree)
    marker = f'name = "{tokens.project}"\nversion = "'
    head, separator, tail = text.partition(marker)
    assert separator, project
    _ = project.write_text(
        f'{head}{marker}{PREVIOUS_VERSION}"{tail.partition(chr(34))[2]}',
        encoding="utf-8",
    )


def _loosen_the_policy(tree: Path) -> None:
    policy = tree / POLICY_FILE
    text = policy.read_text(encoding="utf-8")
    assert text.count(POLICY_EXCLUSIONS) == 1, POLICY_FILE
    _ = policy.write_text(text.replace(POLICY_EXCLUSIONS, LOOSE_EXCLUSIONS), encoding="utf-8")


def previous_release(root: Path, work: Path) -> Pack:
    """The pack that `OLD` is born from: one release before the current tree."""
    tree = extract_commit(root, work / "previous")
    (tree / ADDED_BY_NEW).unlink()
    _ = (tree / DELETED_BY_NEW).write_text(RETIRED_POLICY, encoding="utf-8")
    replaced = tree / REPLACED_BY_NEW
    _ = replaced.write_text(REPLACEMENT_LINE + replaced.read_text("utf-8"), encoding="utf-8")
    _loosen_the_policy(tree)
    _lower_the_version(tree)
    recorded = write_manifest(tree)
    assert recorded.code == 0, recorded.text
    _ = make_repository(tree, "The previous release")
    wheel = build_wheel(tree, work / "dist-previous")
    return Pack(
        root=tree,
        wheel=wheel,
        script=install_tool(wheel, work, "previous"),
        tokens=pack_tokens(tree),
    )


def stale_release(root: Path, work: Path) -> Pack:
    """A pack whose own manifest disagrees with its own tree, for refusal `U8`."""
    tree = extract_commit(root, work / "stale")
    policy = tree / POLICY_FILE
    _ = policy.write_text(policy.read_text("utf-8") + "# A byte the record misses.\n", "utf-8")
    _ = make_repository(tree, "A release with a stale record")
    wheel = build_wheel(tree, work / "dist-stale")
    return Pack(
        root=tree,
        wheel=wheel,
        script=install_tool(wheel, work, "stale"),
        tokens=pack_tokens(tree),
    )


def claiming_release(root: Path, work: Path) -> Pack:
    """A pack whose record claims a user-owned path, for refusal `U6`.

    The update reads the plan through the ownership predicate before it touches
    a file, and a plan can hold a user-owned path only when the pack itself
    ships a record that names one. The record of this release therefore names
    the product document of every project.
    """
    tree = extract_commit(root, work / "claiming")
    recorded = write_manifest(tree)
    assert recorded.code == 0, recorded.text
    manifest = tree / MANIFEST_PATH
    record = cast("dict[str, object]", json.loads(manifest.read_text("utf-8")))
    claimed = cast("dict[str, str]", record["root"])
    claimed[CLAIMED_PATH] = sha256((tree / CLAIMED_PATH).read_bytes()).hexdigest()
    _ = manifest.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", "utf-8")
    _ = make_repository(tree, "A release that claims a user-owned path")
    wheel = build_wheel(tree, work / "dist-claiming")
    return Pack(
        root=tree,
        wheel=wheel,
        script=install_tool(wheel, work, "claiming"),
        tokens=pack_tokens(tree),
    )


def overlay_release(root: Path, work: Path) -> Pack:
    """A pack whose `initial/` holds a file that shadows nothing, for refusal `R9`.

    Every other refusal fires against the shipped pack, from a requested identity
    alone. `R9` cannot: the overlay shadows nothing only when the pack itself
    carries one more starting file, so this release adds one.
    """
    tree = extract_commit(root, work / "overlay")
    tokens = pack_tokens(tree)
    starting = tree / SOURCE_DIRECTORY / tokens.package / CAPABILITY_DIRECTORY / STARTING_FILES
    _ = (starting / UNSHADOWED_FILE).write_text("A file that shadows nothing.\n", "utf-8")
    _ = make_repository(tree, "A release whose overlay adds a file")
    wheel = build_wheel(tree, work / "dist-overlay")
    return Pack(
        root=tree,
        wheel=wheel,
        script=install_tool(wheel, work, "overlay"),
        tokens=tokens,
    )


def clear(tree: Path) -> None:
    """Delete one throwaway tree, whatever it holds."""
    shutil.rmtree(tree, ignore_errors=True)
