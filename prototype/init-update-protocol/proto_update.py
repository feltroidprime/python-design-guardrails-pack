"""PROTOTYPE — wipe me. Answers wayfinder ticket #82.

Question: what minimal external CLI, provenance record, version transition,
drift detection, refusal, and recovery behaviour lets the installed Root Pack
initialise and update ONLY whole pack-owned files, while no generator or
updater code is ever shipped into a Terminal Project?

Run:  python3 proto_update.py [scenario]
      scenario = all | invariant | update | drift | refuse | recover | shims | tar

It materialises a scratch Root Pack v0.3.0, projects it twice under different
names, publishes a v0.4.0 with a real add/replace/delete on the pack-owned
surface, and runs the update against real files and real git. Nothing is mocked.

Inherited and NOT re-decided here:
  #83 projection = copy, swap two tokens, overlay initial/, delete bootstrap
  #86 pack-owned = pack/ + `_`-prefixed names and py.typed under src/<pkg>/
      user-owned = everything else; update writes only pack-owned paths
  #89 command line = <project> <capability> <function>
  #80 the installed pack carries its tree as <package>/_pack.tar
"""

from __future__ import annotations

import filecmp
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).parent
WORK = HERE / "work"

PACK_NAME = "pyrepo"
PACK_PKG = "guardrails_pack"
MANIFEST = "pack/manifest.json"

# ==========================================================================
# The scratch Root Pack. Small, but structurally honest: every ownership
# category from #86 is represented by at least one real file.
# ==========================================================================

# --- pack-owned: pack/ at the root -----------------------------------------
PACK_FILES_V1 = {
    "pack/ruff.toml": 'line-length = 100\nselect = ["E", "F", "I"]\n',
    "pack/justfile": 'gate:\n    python3 pack/scripts/quality_gate.py\n',
    "pack/architecture.toml": '[layers]\nfoundation = "_foundation"\n',
    "pack/scripts/quality_gate.py": 'def main() -> int:\n    return 0\n',
    "pack/scripts/ownership_guard.py": '# four-zone ownership check\ndef main() -> int:\n    return 0\n',
    "pack/tests/test_foundation.py": 'def test_router_exists() -> None:\n    assert True\n',
}

# --- pack-owned: `_`-prefixed names and py.typed under src/<pkg>/ ----------
# NOTE the relative import. An absolute `from guardrails_pack import composition`
# would put the pack token inside a pack-owned file and break byte-identity.
PKG_FILES_V1 = {
    "__init__.py": '__all__: tuple[str, ...] = ()\n',
    "py.typed": "",
    "_foundation/router.py": (
        "from .. import composition\n"
        "\n"
        "def run(argv: list[str]) -> int:\n"
        "    del argv, composition\n"
        "    return 0\n"
    ),
    "_foundation/adapters/clock.py": "import time\n\ndef now() -> float:\n    return time.time()\n",
}

# --- user-owned: identity, policy, seeds, capabilities ---------------------
USER_FILES = {
    "pyproject.toml": (
        "[project]\n"
        f'name = "{PACK_NAME}"\n'
        'version = "0.3.0"\n'
        'dependencies = ["icontract>=2.7.3"]\n'
        "\n"
        "[project.scripts]\n"
        f'{PACK_NAME} = "{PACK_PKG}.cli:main"\n'
        "\n"
        "[tool.ruff]\n"
        "line-length = 100\n"
    ),
    "README.md": f"# {PACK_NAME}\n\nThe Root Pack itself.\n",
    "CHANGELOG.md": "# Changelog\n\n## 0.3.0\n- the pack\n",
    "tests/test_widget.py": "def test_widget() -> None:\n    assert True\n",
}

# --- user-owned thin shims: paths fixed by the tools that read them --------
SHIM_FILES_V1 = {
    "justfile": "import 'pack/justfile'\n\nrun:\n    uv run pyrepo\n",
    ".python-version": "3.14\n",
    ".github/workflows/quality.yml": (
        "name: quality\n"
        "on: [push]\n"
        "jobs:\n"
        "  gate:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - run: just gate\n"
    ),
}

# --- user-owned seeds: written once by init, never by update ---------------
SEED_PKG_FILES = {
    "cli.py": "from ._foundation.router import run\n\ndef main() -> int:\n    return run([])\n",
    "composition.py": "CAPABILITIES: tuple[object, ...] = ()\n",
}

# --- the One-shot Bootstrap capability: deleted by projection --------------
BOOTSTRAP_FILES = {
    "bootstrap/api.py": "def init(name: str) -> int:\n    del name\n    return 0\n",
    "bootstrap/initial/README.md": "# {name}\n\nA new project.\n",
    "bootstrap/initial/CHANGELOG.md": "# Changelog\n\n## 0.3.0\n- created\n",
    f"bootstrap/initial/src/{PACK_PKG}/composition.py": "CAPABILITIES: tuple[object, ...] = ()\n",
}

# --- the Root Pack's own composition root composes bootstrap --------------
ROOT_COMPOSITION = "from .bootstrap import api\n\nCAPABILITIES: tuple[object, ...] = (api,)\n"


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def materialise_root_pack(root: Path, version: str = "0.3.0") -> Path:
    """Write a complete scratch Root Pack at `root`."""
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    for rel, text in PACK_FILES_V1.items():
        write(root, rel, text)
    for rel, text in PKG_FILES_V1.items():
        write(root, f"src/{PACK_PKG}/{rel}", text)
    for rel, text in SEED_PKG_FILES.items():
        write(root, f"src/{PACK_PKG}/{rel}", text)
    for rel, text in BOOTSTRAP_FILES.items():
        write(root, f"src/{PACK_PKG}/{rel}", text)
    for rel, text in {**USER_FILES, **SHIM_FILES_V1}.items():
        write(root, rel, text.replace("0.3.0", version))
    # the Root Pack's own composition root differs from a Terminal Project's
    write(root, f"src/{PACK_PKG}/composition.py", ROOT_COMPOSITION)
    build_manifest(root, PACK_PKG, version)
    return root


# ==========================================================================
# Ownership predicate (#86) and the provenance record
# ==========================================================================


def is_pack_owned_root(rel: str) -> bool:
    return rel == "pack" or rel.startswith("pack/")


def is_pack_owned_pkg(rel: str) -> bool:
    """`rel` is relative to src/<pkg>/."""
    first = rel.split("/")[0]
    return first.startswith("_") or rel == "py.typed"


def may_write(rel: str, pkg: str) -> bool:
    """The write rule, as the PREDICATE #86 asked for — never as a path list.

    A path list cannot express a deletion: a file the new pack dropped is absent
    from the new manifest, yet the update must still be allowed to remove it.
    """
    if is_pack_owned_root(rel):
        return True
    prefix = f"src/{pkg}/"
    return rel.startswith(prefix) and is_pack_owned_pkg(rel[len(prefix) :])


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def walk(base: Path) -> list[str]:
    out = []
    for p in sorted(base.rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            out.append(p.relative_to(base).as_posix())
    return out


def build_manifest(root: Path, pkg: str, version: str) -> dict:
    """Generate pack/manifest.json.

    THREE sections, and NO identity token in any of them:
      root    — literal paths under pack/
      package — paths relative to src/<pkg>/, so the package name never appears
      shims   — user-owned paths, recorded only so `update` can tell a
                customised shim from an untouched one. Never written by update.
    """
    manifest_path = root / MANIFEST
    root_files, pkg_files, shims = {}, {}, {}
    src = root / "src" / pkg
    for rel in walk(root):
        p = root / rel
        if is_pack_owned_root(rel):
            if rel != MANIFEST:  # the manifest cannot hash itself
                root_files[rel] = sha(p)
        elif rel.startswith(f"src/{pkg}/"):
            inner = p.relative_to(src).as_posix()
            if is_pack_owned_pkg(inner):
                pkg_files[inner] = sha(p)
        elif rel in SHIM_FILES_V1:
            shims[rel] = sha(p)
    data = {
        "pack_version": version,
        "root": root_files,
        "package": pkg_files,
        "shims": shims,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return data


# ==========================================================================
# init — the projection of #83, reduced to what this ticket needs
# ==========================================================================


PATH_RENAMES: list[int] = []


class Refusal(Exception):
    """Refuse before writing. The message names the rule."""


def project(pack_root: Path, dest: Path, name: str) -> Path:
    pkg = name.replace("-", "_")
    if dest.exists():
        raise Refusal("R5: destination directory already exists")
    if name in (PACK_NAME, PACK_PKG) or pkg in (PACK_NAME, PACK_PKG):
        raise Refusal("R4: the project name equals a pack token")
    staging = Path(tempfile.mkdtemp(dir=dest.parent, prefix=".proto-"))
    tree = staging / "t"
    shutil.copytree(pack_root, tree)
    # 2. swap the two identity tokens across every text file
    for rel in walk(tree):
        p = tree / rel
        try:
            text = p.read_text()
        except UnicodeDecodeError:
            continue
        new = text.replace(PACK_PKG, pkg).replace(PACK_NAME, name)
        if new != text:
            p.write_text(new)
    # ... and rename EVERY path component that is a pack token, not just src/<pkg>/.
    # FINDING: #83 says "plus one directory rename (src/<package>/)". That is wrong.
    # bootstrap/initial/src/<pkg>/composition.py is a second occurrence, and it
    # shadows nothing unless its path is swapped too.
    renamed = 0
    for p in sorted(tree.rglob("*"), key=lambda q: len(q.parts), reverse=True):
        if p.name in (PACK_PKG, PACK_NAME):
            p.rename(p.parent / (pkg if p.name == PACK_PKG else name))
            renamed += 1
    PATH_RENAMES.append(renamed)
    # 3. overlay initial/, then 4. delete the bootstrap capability
    initial = tree / "src" / pkg / "bootstrap" / "initial"
    for rel in walk(initial):
        target = tree / rel
        if not target.exists():
            raise Refusal(f"R9: initial/{rel} shadows nothing")
        target.write_text((initial / rel).read_text().replace("{name}", name))
    shutil.rmtree(tree / "src" / pkg / "bootstrap")
    # post-checks against the staging tree — nothing is on the user's disk yet
    for rel in walk(tree):
        p = tree / rel
        try:
            text = p.read_text()
        except UnicodeDecodeError:
            continue
        if PACK_PKG in text or PACK_NAME in text:
            raise Refusal(f"R7: {rel} still contains a pack token")
    tree.rename(dest)
    shutil.rmtree(staging, ignore_errors=True)
    return dest


# ==========================================================================
# update — the whole point of this ticket
# ==========================================================================


@dataclass
class Plan:
    old_version: str
    new_version: str
    add: list[str] = field(default_factory=list)
    replace: list[str] = field(default_factory=list)
    delete: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    drifted: list[str] = field(default_factory=list)
    shim_changed: list[str] = field(default_factory=list)
    shim_customised: list[str] = field(default_factory=list)

    @property
    def writes(self) -> list[str]:
        # the provenance record is written LAST, so a crash never leaves a tree
        # claiming a version it does not have
        rest = sorted(r for r in self.add + self.replace + self.delete if r != MANIFEST)
        return rest + ([MANIFEST] if MANIFEST in self.replace else [])


def git(dest: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(dest), *args], capture_output=True, text=True, check=check
    )


def derive_package(dest: Path) -> str:
    src = dest / "src"
    dirs = [p.name for p in sorted(src.iterdir()) if p.is_dir()] if src.is_dir() else []
    if len(dirs) != 1:
        raise Refusal(f"U2: cannot derive the package: src/ holds {len(dirs)} directories")
    return dirs[0]


def flat(manifest: dict, pkg: str) -> dict[str, str]:
    """The manifest's two pack-owned sections as one path -> hash map."""
    out = dict(manifest["root"])
    for rel, h in manifest["package"].items():
        out[f"src/{pkg}/{rel}"] = h
    return out


def plan_update(pack_root: Path, dest: Path, *, require_git: bool = True) -> tuple[Plan, str]:
    old_path = dest / MANIFEST
    if not old_path.is_file():
        raise Refusal("U1: no pack/manifest.json — this is not a Terminal Project")
    pkg = derive_package(dest)
    if (dest / "src" / pkg / "bootstrap").is_dir():
        raise Refusal("U7: a bootstrap capability is present — this is a Root Pack")
    old = json.loads(old_path.read_text())
    new = json.loads((pack_root / MANIFEST).read_text())
    if version_tuple(new["pack_version"]) < version_tuple(old["pack_version"]):
        raise Refusal(
            f"U3: installed pack {new['pack_version']} is older than "
            f"the project's {old['pack_version']} — downgrade refused"
        )
    if require_git:
        if not (dest / ".git").exists():
            raise Refusal("U4: not a git repository — update has no undo without git")
        if git(dest, "status", "--porcelain").stdout.strip():
            raise Refusal("U4: the git worktree is dirty — commit or stash first")
    stale = [r for r, h in new["root"].items() if r != MANIFEST and sha(pack_root / r) != h]
    if stale:
        raise Refusal(f"U8: the installed pack's own manifest is stale: {stale}")

    old_flat, new_flat = flat(old, pkg), flat(new, pkg)
    p = Plan(old["pack_version"], new["pack_version"])
    for rel, h in sorted(new_flat.items()):
        if rel not in old_flat:
            p.add.append(rel)
        elif old_flat[rel] != h:
            p.replace.append(rel)
        else:
            p.unchanged.append(rel)
    for rel in sorted(old_flat):
        if rel not in new_flat:
            p.delete.append(rel)
    # drift: what is on disk now versus what this project was born with
    for rel, h in sorted(old_flat.items()):
        on_disk = dest / rel
        if not on_disk.is_file() or sha(on_disk) != h:
            p.drifted.append(rel)
    # FINDING: the manifest cannot hash itself, so it never lands in add/replace
    # by comparison. Without this line the update is NOT idempotent: the project
    # keeps claiming its old version and re-runs the same writes for ever.
    if p.add or p.replace or p.delete or p.old_version != p.new_version:
        p.replace.append(MANIFEST)
    # shim report: only nag when the pack changed a shim the user did NOT touch
    for rel, h in sorted(new["shims"].items()):
        if old["shims"].get(rel) == h:
            continue
        p.shim_changed.append(rel)
        if (dest / rel).is_file() and sha(dest / rel) != old["shims"].get(rel):
            p.shim_customised.append(rel)
    return p, pkg


def apply_update(
    pack_root: Path,
    dest: Path,
    plan: Plan,
    pkg: str,
    *,
    on_drift: str = "refuse",
    drift_scope: str = "written",
    fail_after: int | None = None,
) -> list[str]:
    """Write only pack-owned paths. Transactional: any failure restores everything."""
    drifted = set(plan.drifted)
    # scope "written": only drift on a file this update rewrites counts.
    # scope "all":     every drifted pack-owned file counts, including files the
    #                  new version leaves alone — the only scope under which the
    #                  manifest still describes the disk when the update finishes.
    touched = [r for r in plan.writes if r in drifted] if drift_scope == "written" else sorted(drifted)
    if touched and on_drift == "refuse":
        raise Refusal(f"U5: {len(touched)} pack-owned file(s) drifted: {touched}")
    todo = [r for r in plan.writes if not (touched and on_drift == "skip" and r in drifted)]
    if on_drift == "backup" and drift_scope == "all":
        todo = [r for r in touched if r not in todo] + todo  # restore drifted-but-unchanged too
    illegal = [r for r in todo if not may_write(r, pkg)]
    if illegal:  # the safety rule, executable
        raise Refusal(f"U6: update would write user-owned paths: {illegal}")

    snapshot = Path(tempfile.mkdtemp(prefix=".proto-undo-"))
    for rel in todo:
        src = dest / rel
        if src.is_file():
            (snapshot / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, snapshot / rel)
    written: list[str] = []
    try:
        for n, rel in enumerate(todo):
            if fail_after is not None and n == fail_after:
                raise OSError("simulated crash mid-write")
            target = dest / rel
            if rel in plan.delete:
                target.unlink(missing_ok=True)
            else:
                source = pack_root / rel.replace(f"src/{pkg}/", f"src/{PACK_PKG}/", 1)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            written.append(rel)
        if on_drift == "backup" and touched:
            for rel in touched:
                if (snapshot / rel).is_file():
                    keep = dest / "pack" / ".drift" / rel
                    keep.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(snapshot / rel, keep)
    except Exception:
        for rel in written:  # restore, so a crash leaves the tree untouched
            saved = snapshot / rel
            target = dest / rel
            if saved.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(saved, target)
            else:
                target.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(snapshot, ignore_errors=True)
    return written


def version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


# ==========================================================================
# publishing v0.4.0 — one real add, one replace, one delete, one shim change
# ==========================================================================


def publish_v2(root: Path) -> None:
    write(root, "pack/scripts/quality_gate.py", "def main() -> int:\n    print('v2 gate')\n    return 0\n")
    write(root, "pack/scripts/capability_guard.py", "def main() -> int:\n    return 0\n")  # ADD
    (root / "pack/scripts/ownership_guard.py").unlink()  # DELETE: four zones died
    write(
        root,
        f"src/{PACK_PKG}/_foundation/router.py",
        "from .. import composition\n\ndef run(argv: list[str]) -> int:\n"
        "    del argv, composition\n    return 1\n",
    )
    write(  # shim rot: only the pinned action version changes
        root,
        ".github/workflows/quality.yml",
        SHIM_FILES_V1[".github/workflows/quality.yml"].replace("checkout@v4", "checkout@v5"),
    )
    write(root, "pyproject.toml", USER_FILES["pyproject.toml"].replace("0.3.0", "0.4.0"))
    build_manifest(root, PACK_PKG, "0.4.0")


def make_git_repo(dest: Path) -> None:
    git(dest, "init", "-q")
    git(dest, "config", "user.email", "proto@example.invalid")
    git(dest, "config", "user.name", "proto")
    git(dest, "add", "-A")
    git(dest, "commit", "-qm", "init")


# ==========================================================================
# scenarios
# ==========================================================================

RESULTS: list[tuple[str, str]] = []


def report(label: str, outcome: str) -> None:
    RESULTS.append((label, outcome))
    print(f"  {label:<52} {outcome}")


def fresh(name: str) -> Path:
    d = WORK / name
    if d.exists():
        shutil.rmtree(d)
    d.parent.mkdir(parents=True, exist_ok=True)
    return d


def setup(tag: str, project_name: str = "my-product") -> tuple[Path, Path]:
    root = materialise_root_pack(fresh(f"{tag}-root"))
    dest = project(root, fresh(f"{tag}-{project_name}"), project_name)
    make_git_repo(dest)
    return root, dest


def scenario_invariant() -> None:
    print("\n[invariant] two projections, one pack-owned surface")
    root = materialise_root_pack(fresh("inv-root"))
    a = project(root, fresh("inv-a"), "my-product")
    b = project(root, fresh("inv-b"), "other-thing")
    man = json.loads((a / MANIFEST).read_text())
    pack_a = sorted(man["root"]) + sorted(f"src/my_product/{r}" for r in man["package"])
    pack_b = sorted(man["root"]) + sorted(f"src/other_thing/{r}" for r in man["package"])
    same = all(filecmp.cmp(a / x, b / y, shallow=False) for x, y in zip(pack_a, pack_b))
    report(f"{len(pack_a)} pack-owned files byte-identical across projects", "yes" if same else "NO")
    leaked = [r for r in pack_a if PACK_PKG in (a / r).read_text() or PACK_NAME in (a / r).read_text()]
    report("pack token inside a pack-owned file", f"{len(leaked)} occurrence(s)")
    report("manifest itself is pack-owned and identical", "yes" if filecmp.cmp(a / MANIFEST, b / MANIFEST, shallow=False) else "NO")
    user = [r for r in walk(a) if r not in pack_a and not r.startswith("src/my_product/")]
    report("user-owned root files the manifest may not touch", str(len(user)))


def scenario_update() -> None:
    print("\n[update] 0.3.0 -> 0.4.0, add + replace + delete")
    root, dest = setup("upd")
    before = {r: sha(dest / r) for r in walk(dest) if not r.startswith(".git")}
    publish_v2(root)
    plan, pkg = plan_update(root, dest)
    report("version transition", f"{plan.old_version} -> {plan.new_version}")
    report("classified add / replace / delete / unchanged",
           f"{len(plan.add)} / {len(plan.replace)} / {len(plan.delete)} / {len(plan.unchanged)}")
    written = apply_update(root, dest, plan, pkg)
    report("paths written", str(len(written)))
    after = {r: sha(dest / r) for r in walk(dest) if not r.startswith(".git")}
    changed = sorted(set(before) ^ set(after)) + sorted(
        r for r in set(before) & set(after) if before[r] != after[r]
    )
    user_changed = [r for r in changed if not may_write(r, pkg)]
    report("user-owned files changed by update", f"{len(user_changed)} {user_changed}")
    report("deleted file gone from disk", "yes" if not (dest / "pack/scripts/ownership_guard.py").exists() else "NO")
    report("added file present", "yes" if (dest / "pack/scripts/capability_guard.py").exists() else "NO")
    report("manifest now records", json.loads((dest / MANIFEST).read_text())["pack_version"])
    # second run must be a no-op
    make_git_repo_recommit(dest)
    plan2, _ = plan_update(root, dest)
    report("re-run writes", f"{len(plan2.writes)} paths (idempotent)" if not plan2.writes else "NOT idempotent")


def make_git_repo_recommit(dest: Path) -> None:
    git(dest, "add", "-A")
    git(dest, "commit", "-qm", "update")


def scenario_drift() -> None:
    print("\n[drift] the user edited a pack-owned file")
    for policy, scope in (
        ("refuse", "written"),
        ("skip", "written"),
        ("backup", "written"),
        ("refuse", "all"),
        ("backup", "all"),
    ):
        policy_label = f"{policy}/{scope}"
        root, dest = setup(f"drift-{policy}-{scope}")
        (dest / "pack/scripts/quality_gate.py").write_text("# my local hack\ndef main(): return 0\n")
        (dest / "pack/architecture.toml").write_text("[layers]\nmine = true\n")  # drifted, not updated
        make_git_repo_recommit(dest)
        publish_v2(root)
        plan, pkg = plan_update(root, dest)
        report(f"[{policy_label}] drift detected", f"{len(plan.drifted)} file(s)")
        try:
            written = apply_update(root, dest, plan, pkg, on_drift=policy, drift_scope=scope)
        except Refusal as exc:
            report(f"[{policy_label}] outcome", f"refused, {str(exc)[:44]}")
            report(f"[{policy_label}] files changed", "0")
            continue
        hacked = "my local hack" in (dest / "pack/scripts/quality_gate.py").read_text()
        report(f"[{policy_label}] outcome", f"wrote {len(written)} path(s)")
        report(f"[{policy_label}] user's edit survives", "yes" if hacked else "no, overwritten")
        kept = dest / "pack/.drift/pack/scripts/quality_gate.py"
        report(f"[{policy_label}] recoverable copy", "pack/.drift/…" if kept.exists() else "none (git only)")
        after = json.loads((dest / MANIFEST).read_text())
        live = flat(after, pkg)
        lying = [r for r, h in live.items() if (dest / r).is_file() and sha(dest / r) != h]
        report(f"[{policy_label}] manifest disagrees with disk", f"{len(lying)} file(s)")


def scenario_refuse() -> None:
    print("\n[refuse] every refusal rule, against a real tree")
    root, dest = setup("ref")
    cases: list[tuple[str, callable]] = []

    empty = fresh("ref-empty")
    empty.mkdir(parents=True)
    cases.append(("U1 not a Terminal Project", lambda: plan_update(root, empty)))

    two = fresh("ref-two")
    shutil.copytree(dest, two)
    (two / "src" / "second_pkg").mkdir()
    cases.append(("U2 two packages under src/", lambda: plan_update(root, two)))

    newer = fresh("ref-newer")
    shutil.copytree(dest, newer)
    m = json.loads((newer / MANIFEST).read_text())
    m["pack_version"] = "0.9.0"
    (newer / MANIFEST).write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    cases.append(("U3 downgrade", lambda: plan_update(root, newer)))

    dirty = fresh("ref-dirty")
    shutil.copytree(dest, dirty)
    (dirty / "README.md").write_text("edited\n")
    cases.append(("U4 dirty git worktree", lambda: plan_update(root, dirty)))

    nogit = fresh("ref-nogit")
    shutil.copytree(dest, nogit)
    shutil.rmtree(nogit / ".git")
    cases.append(("U4 not a git repository", lambda: plan_update(root, nogit)))

    cases.append(("U7 destination is a Root Pack", lambda: plan_update(root, root, require_git=False)))

    stale_root = materialise_root_pack(fresh("ref-stale-root"))
    write(stale_root, "pack/ruff.toml", "line-length = 1\n")  # tree edited, manifest not rebuilt
    cases.append(("U8 installed pack's manifest is stale", lambda: plan_update(stale_root, dest)))

    cases.append(("R5 init onto an existing directory", lambda: project(root, dest, "my-product")))
    cases.append(("R4 project named after the pack", lambda: project(root, fresh("ref-x"), PACK_NAME)))

    for label, run in cases:
        try:
            run()
            report(label, "NOT REFUSED")
        except Refusal as exc:
            report(label, f"refused: {str(exc)[:58]}")

    equal_root = materialise_root_pack(fresh("ref-equal-root"))
    plan, _ = plan_update(equal_root, dest)
    report("equal version is a no-op, not a refusal", f"{len(plan.writes)} paths, exit 0")


def scenario_recover() -> None:
    print("\n[recover] a crash mid-write, and the undo")
    root, dest = setup("rec")
    publish_v2(root)
    plan, pkg = plan_update(root, dest)
    before = {r: sha(dest / r) for r in walk(dest) if not r.startswith(".git")}
    try:
        apply_update(root, dest, plan, pkg, fail_after=2)
    except OSError as exc:
        report("crash after 2 of %d writes" % len(plan.writes), str(exc))
    after = {r: sha(dest / r) for r in walk(dest) if not r.startswith(".git")}
    report("tree after the crash", "identical" if before == after else "CORRUPT")
    report("git sees", f"{len(git(dest, 'status', '--porcelain').stdout.split())} dirty entries")
    written = apply_update(root, dest, plan, pkg)
    report("retry after the crash", f"wrote {len(written)} path(s)")
    git(dest, "checkout", "--", ".")
    git(dest, "clean", "-qfd")
    report("git checkout -- . && git clean -fd restores 0.3.0",
           json.loads((dest / MANIFEST).read_text())["pack_version"])


def scenario_shims() -> None:
    print("\n[shims] user-owned entry points the update may never write")
    root, dest = setup("shim")
    custom = fresh("shim-custom")
    shutil.copytree(dest, custom)
    (custom / ".github/workflows/quality.yml").write_text(
        SHIM_FILES_V1[".github/workflows/quality.yml"].replace("[push]", "[push, pull_request]")
    )
    make_git_repo_recommit(custom)
    publish_v2(root)
    for label, target in (("untouched shim", dest), ("customised shim", custom)):
        plan, pkg = plan_update(root, target)
        before = sha(target / ".github/workflows/quality.yml")
        apply_update(root, target, plan, pkg)
        after = sha(target / ".github/workflows/quality.yml")
        report(f"[{label}] pack changed shims", f"{plan.shim_changed}")
        report(f"[{label}] flagged as customised", f"{plan.shim_customised}")
        report(f"[{label}] shim rewritten by update", "NO (correct)" if before == after else "YES — BUG")


def scenario_tar() -> None:
    print("\n[tar] the installed pack reads its tree from <package>/_pack.tar")
    root = materialise_root_pack(fresh("tar-root"))
    publish_v2(root)
    blob = fresh("tar-blob") / "_pack.tar"
    blob.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(blob, "w") as tar:
        for rel in walk(root):
            tar.add(root / rel, arcname=rel)
    extracted = fresh("tar-extracted")
    with tarfile.open(blob) as tar:
        tar.extractall(extracted, filter="data")
    report("blob size", f"{blob.stat().st_size} bytes, {len(walk(extracted))} files")
    root2, dest = setup("tar-proj")
    del root2
    plan, pkg = plan_update(extracted, dest)
    written = apply_update(extracted, dest, plan, pkg)
    report("update driven from the extracted blob", f"wrote {len(written)} path(s)")
    report("result version", json.loads((dest / MANIFEST).read_text())["pack_version"])


SCENARIOS = {
    "invariant": scenario_invariant,
    "update": scenario_update,
    "drift": scenario_drift,
    "refuse": scenario_refuse,
    "recover": scenario_recover,
    "shims": scenario_shims,
    "tar": scenario_tar,
}


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if WORK.exists():
        shutil.rmtree(WORK)
    names = list(SCENARIOS) if which == "all" else [which]
    for n in names:
        SCENARIOS[n]()
    print(f"\n{len(RESULTS)} measurements. work tree: {WORK}")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("GIT_CONFIG_GLOBAL", "/dev/null")
    raise SystemExit(main())
