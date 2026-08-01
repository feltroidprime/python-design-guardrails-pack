"""PROTOTYPE — wipe me. Answers wayfinder ticket #80.

Question: can ONE valid root pyproject.toml and ONE real project tree support
  (1) Root Pack development,
  (2) distribution of the external CLI via `uv tool install`,
  (3) closed identity projection,
  (4) creation of a valid Terminal Project,
without a second pyproject, a Jinja source tree, or a hidden template copy?

Run:  python3 proto_pack.py [variant]   variant = hatchling | uvbuild | archive | both
It materializes a scratch Root Pack, builds a wheel, installs it into a throwaway
tool env, runs `pyrepo init my-product`, and then checks the Terminal Project.
Every step prints its real result. Nothing is mocked.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).parent
WORK = HERE / "work"

PACK_NAME = "pyrepo"
PACK_PKG = "guardrails_pack"
TERMINAL_NAME = "my-product"
TERMINAL_PKG = "my_product"

# --------------------------------------------------------------------------
# The one file under test, in three packaging variants.
# --------------------------------------------------------------------------

SHARED_POLICY = f"""
[tool.uv]
required-version = ">=0.12.0,<0.13"

[dependency-groups]
dev = ["pytest>=9.1.1", "ruff>=0.15.21"]

[tool.ruff]
line-length = 100
src = ["src", "tests", "scripts"]

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I", "UP"]

[tool.ruff.lint.isort]
known-first-party = ["{PACK_PKG}", "scripts", "tests"]

[tool.pytest.ini_options]
minversion = "9.1"
testpaths = ["tests"]
addopts = ["-ra", "--strict-config", "--strict-markers"]
"""

# Variant A: hatchling. force-include lifts real root files into package data.
PYPROJECT_HATCHLING = f"""\
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{PACK_NAME}"
version = "0.3.0"
description = "A Python 3.14 application with an executable architecture and quality contract."
readme = "README.md"
requires-python = ">=3.14,<3.15"
dependencies = []

[project.scripts]
{PACK_NAME} = "{PACK_PKG}.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/{PACK_PKG}"]

# The One-shot Bootstrap needs the tree it projects. force-include lifts the real
# root files into package data at build time, so no copy exists in the source tree.
[tool.hatch.build.targets.wheel.force-include]
"pyproject.toml" = "{PACK_PKG}/_pack_tree/pyproject.toml"
"README.md" = "{PACK_PKG}/_pack_tree/README.md"
"CHANGELOG.md" = "{PACK_PKG}/_pack_tree/CHANGELOG.md"
"AGENTS.md" = "{PACK_PKG}/_pack_tree/AGENTS.md"
"justfile" = "{PACK_PKG}/_pack_tree/justfile"
"scripts" = "{PACK_PKG}/_pack_tree/scripts"
"tests" = "{PACK_PKG}/_pack_tree/tests"
"src" = "{PACK_PKG}/_pack_tree/src"
{SHARED_POLICY}"""

# Variant B: uv_build. It cannot reach outside the module root, so `just build`
# stages the tree into src/<pkg>/_pack_tree first — a generated, gitignored copy.
# The pyproject then declares NO pack-only packaging: inclusion is by presence.
PYPROJECT_UVBUILD = f"""\
[build-system]
requires = ["uv_build==0.12.0"]
build-backend = "uv_build"

[project]
name = "{PACK_NAME}"
version = "0.3.0"
description = "A Python 3.14 application with an executable architecture and quality contract."
readme = "README.md"
requires-python = ">=3.14,<3.15"
dependencies = []

[project.scripts]
{PACK_NAME} = "{PACK_PKG}.cli:main"

[tool.uv.build-backend]
module-name = "{PACK_PKG}"
{SHARED_POLICY}"""

# --------------------------------------------------------------------------
# The rest of the scratch Root Pack.
# --------------------------------------------------------------------------

CLI_PY = f'''\
"""Command line for {PACK_NAME}. Subcommands are discovered by scanning the
capabilities directory; no registry and no generated index."""

from __future__ import annotations

import importlib
import pkgutil
import sys
from pathlib import Path


def _subcommands() -> dict[str, object]:
    from {PACK_PKG} import capabilities

    found = {{}}
    for info in pkgutil.iter_modules([str(Path(capabilities.__file__).parent)]):
        try:
            api = importlib.import_module(f"{PACK_PKG}.capabilities.{{info.name}}.api")
        except ModuleNotFoundError:
            continue
        command = getattr(api, "COMMAND", None)
        if command is not None:
            found[command] = api
    return found


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    commands = _subcommands()
    if not argv or argv[0] not in commands:
        print(f"usage: {{Path(sys.argv[0]).name}} {{'|'.join(sorted(commands)) or '<no subcommands>'}}")
        return 2 if argv else 0
    return int(commands[argv[0]].run(argv[1:]))
'''

BOOTSTRAP_API_PY = f'''\
"""One-shot Bootstrap: the only capability the projection removes."""

from __future__ import annotations

from {PACK_PKG}.capabilities.bootstrap.projection import project

COMMAND = "init"


def run(argv: list[str]) -> int:
    if not argv:
        print("usage: init <project-name> [directory]")
        return 2
    name = argv[0]
    destination = argv[1] if len(argv) > 1 else name
    return project(name, destination)
'''

PROJECTION_PY = f'''\
"""Copy the Root Pack tree, swap two identity tokens, overlay the starting
files, delete this capability. No template engine, no interior editing."""

from __future__ import annotations

import keyword
import re
import shutil
import tempfile
from pathlib import Path

PACK_NAME = "{PACK_NAME}"
PACK_PKG = "{PACK_PKG}"
SKIP = {{".git", "dist", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "_pack_tree"}}


def pack_tree(scratch: Path) -> Path:
    """Package data first (tarball, then directory), else the live source tree."""
    root = Path(__file__).parents[2]
    archive = root / "_pack.tar"
    if archive.is_file():
        import tarfile

        with tarfile.open(archive) as handle:
            handle.extractall(scratch, filter="data")
        return scratch
    if (root / "_pack_tree").is_dir():
        return root / "_pack_tree"
    return Path(__file__).parents[4]


def _is_text(path: Path) -> bool:
    try:
        path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False
    return True


def _swap(text: str, name: str, package: str) -> str:
    text = re.sub(rf"\\b{{re.escape(PACK_PKG)}}\\b", package, text)
    return re.sub(rf"\\b{{re.escape(PACK_NAME)}}\\b", name, text)


def project(name: str, destination: str) -> int:
    package = name.replace("-", "_")
    target = Path(destination).resolve()

    # Pre-checks (R1-R6 of the projection contract, reduced to what this asks).
    if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
        print(f"refused: {{name!r}} is not a valid distribution name. Nothing was written.")
        return 1
    if not package.isidentifier() or keyword.iskeyword(package):
        print(f"refused: {{package!r}} is not a valid import name. Nothing was written.")
        return 1
    if name in (PACK_NAME, PACK_PKG) or package in (PACK_NAME, PACK_PKG):
        print("refused: the name collides with a pack token. Nothing was written.")
        return 1
    if target.exists():
        print(f"refused: {{target}} already exists. Nothing was written.")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        source = pack_tree(Path(tmp) / "unpacked")
        staged = Path(tmp) / "staged"
        shutil.copytree(source, staged, ignore=shutil.ignore_patterns(*SKIP))

        for path in sorted(staged.rglob("*")):
            if path.is_file() and _is_text(path):
                path.write_text(_swap(path.read_text(encoding="utf-8"), name, package), encoding="utf-8")

        (staged / "src" / PACK_PKG).rename(staged / "src" / package)

        bootstrap = staged / "src" / package / "capabilities" / "bootstrap"
        initial = bootstrap / "initial"
        landed = []
        for start in sorted(initial.iterdir()):
            root_file = staged / start.name
            if not root_file.exists():
                print(f"refused: {{start.name}} had no file to replace. Nothing was written.")
                return 1
            shutil.copy2(start, root_file)
            landed.append(start.name)
        shutil.rmtree(bootstrap)

        # Post-checks (R7-R9).
        for path in sorted(staged.rglob("*")):
            if path.is_file() and _is_text(path):
                body = path.read_text(encoding="utf-8")
                if re.search(rf"\\b({{re.escape(PACK_PKG)}}|{{re.escape(PACK_NAME)}})\\b", body):
                    print(f"refused: {{path}} still contains a pack token. Nothing was written.")
                    return 1
            if path.is_dir() and path.name == "bootstrap":
                print("refused: a bootstrap capability survived. Nothing was written.")
                return 1

        shutil.move(str(staged), str(target))

    print(f"created {{target}} (starting files: {{', '.join(landed)}})")
    return 0
'''

WIDGET_API_PY = '''\
"""An ordinary Product Capability. The projection keeps it untouched."""

from __future__ import annotations


def greet(who: str) -> str:
    return f"hello, {who}"
'''

FILES: dict[str, str] = {
    "README.md": f"# {PACK_NAME}\n\nThe Root Pack. It projects itself once into a Terminal Project.\n",
    "CHANGELOG.md": f"# Changelog — {PACK_NAME}\n\n## 0.3.0\n\n- Root Pack history.\n",
    "AGENTS.md": f"# AGENTS.md\n\nThis repository runs one quality gate. Import the package as `{PACK_PKG}`.\n",
    "justfile": f"check:\n    uv run ruff check .\n    uv run pytest\n\nbuild:\n    uv build\n\n# The console script is named after the project.\nrun *ARGS:\n    uv run {PACK_NAME} {{{{ARGS}}}}\n",
    "scripts/quality_gate.py": 'from __future__ import annotations\n\nimport subprocess\nimport sys\n\n\ndef main() -> int:\n    for command in (["ruff", "check", "."], ["pytest", "-q"]):\n        if subprocess.run(command, check=False).returncode:\n            return 1\n    return 0\n\n\nif __name__ == "__main__":\n    sys.exit(main())\n',
    "tests/test_smoke.py": f'from __future__ import annotations\n\nfrom {PACK_PKG}.capabilities.widget.api import greet\n\n\ndef test_greet():\n    assert greet("world") == "hello, world"\n',
    f"src/{PACK_PKG}/__init__.py": "",
    f"src/{PACK_PKG}/cli.py": CLI_PY,
    f"src/{PACK_PKG}/capabilities/__init__.py": "",
    f"src/{PACK_PKG}/capabilities/widget/__init__.py": "",
    f"src/{PACK_PKG}/capabilities/widget/api.py": WIDGET_API_PY,
    f"src/{PACK_PKG}/capabilities/bootstrap/__init__.py": "",
    f"src/{PACK_PKG}/capabilities/bootstrap/api.py": BOOTSTRAP_API_PY,
    f"src/{PACK_PKG}/capabilities/bootstrap/projection.py": PROJECTION_PY,
    f"src/{PACK_PKG}/capabilities/bootstrap/initial/README.md": "# PROJECT\n\nA new project. Describe it here.\n",
    f"src/{PACK_PKG}/capabilities/bootstrap/initial/CHANGELOG.md": "# Changelog\n\n## 0.3.0\n\n- Created from the pack.\n",
}


# --------------------------------------------------------------------------
# Harness.
# --------------------------------------------------------------------------


def run(command: list[str], cwd: Path, label: str) -> tuple[bool, str]:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    output = (result.stdout + result.stderr).strip()
    ok = result.returncode == 0
    print(f"  [{'OK ' if ok else 'FAIL'}] {label}")
    if not ok:
        print(textwrap.indent(output[-1500:], "        "))
    return ok, output


def materialize(root: Path, pyproject: str) -> None:
    shutil.rmtree(root, ignore_errors=True)
    for relative, body in FILES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    (root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    (root / ".gitignore").write_text(
        "dist/\n.venv/\n__pycache__/\nsrc/*/_pack_tree/\nsrc/*/_pack.tar\n", encoding="utf-8"
    )


def stage_pack_archive(root: Path) -> int:
    """What `just build` runs in the archive variant: one blob, from the commit."""
    for command in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=p@p", "-c", "user.name=p", "commit", "-qm", "proto"],
    ):
        subprocess.run(command, cwd=root, capture_output=True, check=False)
    target = root / "src" / PACK_PKG / "_pack.tar"
    subprocess.run(
        ["git", "archive", "HEAD", "-o", str(target)], cwd=root, capture_output=True, check=True
    )
    import tarfile

    with tarfile.open(target) as handle:
        return len(handle.getnames())


def stage_pack_tree(root: Path) -> int:
    """What `just build` runs before `uv build` in the uv_build variant."""
    staged = root / "src" / PACK_PKG / "_pack_tree"
    shutil.rmtree(staged, ignore_errors=True)
    shutil.copytree(
        root,
        staged,
        ignore=shutil.ignore_patterns(
            ".git", "dist", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "_pack_tree"
        ),
    )
    return sum(1 for p in staged.rglob("*") if p.is_file())


def experiment(variant: str) -> dict[str, bool]:
    print(f"\n=== variant: {variant} ===")
    root = WORK / variant / "rootpack"
    root.parent.mkdir(parents=True, exist_ok=True)
    materialize(root, PYPROJECT_HATCHLING if variant == "hatchling" else PYPROJECT_UVBUILD)
    verdict: dict[str, bool] = {}

    print(" role 1 — Root Pack development")
    verdict["root sync"], _ = run(["uv", "sync", "--quiet"], root, "uv sync")
    verdict["root tests"], _ = run(["uv", "run", "pytest", "-q"], root, "uv run pytest")
    verdict["root cli"], out = run(["uv", "run", PACK_NAME], root, f"uv run {PACK_NAME}")
    print(f"        -> {out.splitlines()[0] if out else ''}")

    print(" role 2 — external CLI distribution")
    if variant == "uvbuild":
        count = stage_pack_tree(root)
        print(f"  [OK ] just build stages src/{PACK_PKG}/_pack_tree ({count} files, gitignored)")
    if variant == "archive":
        count = stage_pack_archive(root)
        print(f"  [OK ] just build stages src/{PACK_PKG}/_pack.tar ({count} entries, gitignored)")
    verdict["build"], _ = run(["uv", "build", "--wheel"], root, "uv build --wheel")
    if variant in {"uvbuild", "archive"}:
        _, findings = run(
            ["uv", "run", "ruff", "check", ".", "--output-format=concise"],
            root,
            "root ruff, with the staged artifact present",
        )
        doubled = len([l for l in findings.splitlines() if "_pack_tree/" in l or "_pack.tar" in l])
        verdict["gate unpolluted"] = doubled == 0
        print(f"  [{'OK ' if not doubled else 'FAIL'}] staged artifact adds no findings ({doubled})")
    wheels = sorted((root / "dist").glob("*.whl"))
    if not wheels:
        return verdict
    tool_dir = WORK / variant / "toolenv"
    shutil.rmtree(tool_dir, ignore_errors=True)
    verdict["venv"], _ = run(["uv", "venv", str(tool_dir)], root, "uv venv (tool env)")
    verdict["install"], _ = run(
        ["uv", "pip", "install", "--python", str(tool_dir / "bin" / "python"), str(wheels[0])],
        root,
        "uv pip install <wheel>",
    )
    installed = tool_dir / "bin" / PACK_NAME

    print(" role 3 — closed identity projection, from the installed CLI only")
    out_dir = WORK / variant / "out"
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    verdict["project"], out = run(
        [str(installed), "init", TERMINAL_NAME, str(out_dir / TERMINAL_NAME)],
        out_dir,
        f"{PACK_NAME} init {TERMINAL_NAME}",
    )
    terminal = out_dir / TERMINAL_NAME
    if not terminal.is_dir():
        print("        -> no Terminal Project produced")
        return verdict
    print(f"        -> {out.splitlines()[-1] if out else ''}")

    print(" role 4 — the Terminal Project is valid")
    verdict["no bootstrap"] = not list(terminal.rglob("bootstrap"))
    print(f"  [{'OK ' if verdict['no bootstrap'] else 'FAIL'}] no bootstrap capability survives")
    leaks = [
        str(p.relative_to(terminal))
        for p in terminal.rglob("*")
        if p.is_file() and _text_leaks(p)
    ]
    verdict["no token leak"] = not leaks
    print(f"  [{'OK ' if not leaks else 'FAIL'}] no pack token leaks")
    if leaks:
        print(f"        -> {leaks[:6]}")
    dead = [
        line for line in (terminal / "pyproject.toml").read_text(encoding="utf-8").splitlines()
        if "_pack_tree" in line or "_pack.tar" in line
    ]
    verdict["terminal pyproject clean"] = not dead
    print(f"  [{'OK ' if not dead else 'FAIL'}] Terminal pyproject.toml carries no pack-only packaging")
    if dead:
        print(f"        -> {len(dead)} surviving lines, e.g. {dead[0].strip()!r}")

    verdict["terminal sync"], _ = run(["uv", "sync", "--quiet"], terminal, "uv sync")
    in_venv = ([*(terminal / ".venv").rglob("_pack_tree"), *(terminal / ".venv").rglob("_pack.tar")]
        if (terminal / ".venv").is_dir() else [])
    verdict["terminal venv clean"] = not in_venv
    print(f"  [{'OK ' if not in_venv else 'FAIL'}] no pack tree lands in the Terminal .venv")
    verdict["terminal tests"], _ = run(["uv", "run", "pytest", "-q"], terminal, "uv run pytest")
    verdict["terminal cli"], out = run(["uv", "run", TERMINAL_NAME], terminal, f"uv run {TERMINAL_NAME}")
    print(f"        -> {out.splitlines()[0] if out else ''}")
    verdict["terminal build"], _ = run(["uv", "build", "--wheel"], terminal, "uv build --wheel")

    # The wart the ticket must judge: what does the Terminal Project's own wheel carry?
    tw = sorted((terminal / "dist").glob("*.whl"))
    if tw:
        _, listing = run(
            [sys.executable, "-c", f"import zipfile;print('\\n'.join(zipfile.ZipFile(r'{tw[0]}').namelist()))"],
            terminal,
            "inspect Terminal Project wheel",
        )
        names = listing.splitlines()
        carried = [n for n in names if "_pack_tree/" in n or "_pack.tar" in n]
        print(f"        -> {len(names)} entries; {len(carried)} under _pack_tree")
        verdict["terminal wheel clean"] = not carried
        print(f"  [{'OK ' if not carried else 'FAIL'}] Terminal Project wheel carries no pack tree")
    return verdict


def _text_leaks(path: Path) -> bool:
    if any(part in {".git", ".venv", "dist", "__pycache__"} for part in path.parts):
        return False
    try:
        body = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False
    import re

    return bool(re.search(rf"\b({PACK_PKG}|{PACK_NAME})\b", body))


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    variants = ["hatchling", "uvbuild", "archive"] if which == "both" else [which]
    table: dict[str, dict[str, bool]] = {}
    for variant in variants:
        table[variant] = experiment(variant)

    print("\n=== summary ===")
    keys: list[str] = []
    for verdict in table.values():
        for key in verdict:
            if key not in keys:
                keys.append(key)
    width = max(len(k) for k in keys) if keys else 10
    header = " " * (width + 2) + "  ".join(v.ljust(10) for v in variants)
    print(header)
    for key in keys:
        row = key.ljust(width + 2)
        for variant in variants:
            value = table[variant].get(key)
            row += ("OK" if value else "FAIL" if value is False else "-").ljust(12)
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
