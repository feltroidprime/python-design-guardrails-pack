"""Deterministic publication-figure tests: stdlib only, offline, fixture driven."""

import csv
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import zlib


REPO_ROOT = Path(__file__).resolve().parents[1]
FIGURE_COMMAND = REPO_ROOT / "benchmarks" / "figures.py"
FIXTURE_REGISTRY = REPO_ROOT / "tests" / "fixtures" / "publication_registry.jsonl"
FIGURES = {
    "quality-vs-time": (
        "probe_pass_rate",
        "judge_primary_rate",
        "wall_time_seconds",
    ),
    "quality-vs-cost": (
        "probe_pass_rate",
        "judge_primary_rate",
        "cost_usd",
    ),
    "effort-actions": ("tool_calls", "turns"),
    "effort-tokens": (
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_tokens",
    ),
}
IDENTITY_COLUMNS = (
    "template_version",
    "provider",
    "model",
    "effort",
    "app",
    "variant",
    "phase",
    "arm",
    "runs",
    "seeds",
)


def _run_export(output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (
            sys.executable,
            str(FIGURE_COMMAND),
            "--registry",
            str(FIXTURE_REGISTRY),
            "--output-dir",
            str(output),
        ),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _png_text(path: Path) -> dict[str, str]:
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    metadata: dict[str, str] = {}
    offset = 8
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if kind == b"tEXt":
            key, value = payload.split(b"\0", 1)
            metadata[key.decode("latin-1")] = value.decode("latin-1")
        if kind == b"IEND":
            break
    return metadata


def _png_pixels(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    width, height = struct.unpack(">II", data[16:24])
    compressed = bytearray()
    offset = 8
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if kind == b"IDAT":
            compressed.extend(payload)
        if kind == b"IEND":
            break
    scanlines = zlib.decompress(compressed)
    stride = width * 3
    pixels = b"".join(
        scanlines[row * (stride + 1) + 1 : (row + 1) * (stride + 1)]
        for row in range(height)
    )
    return width, height, pixels


def test_export_cli_produces_deterministic_full_figure_set_with_exact_csv_data(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    completed = _run_export(first)
    repeated = _run_export(second)

    assert completed.returncode == repeated.returncode == 0, completed.stderr
    assert "Exported 4 publication figures" in completed.stdout
    assert sorted(path.name for path in first.iterdir()) == sorted(
        [f"{name}.{suffix}" for name in FIGURES for suffix in ("csv", "png", "svg")]
        + ["manifest.json"]
    )
    assert {
        path.name: path.read_bytes() for path in first.iterdir()
    } == {path.name: path.read_bytes() for path in second.iterdir()}

    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source"] == str(FIXTURE_REGISTRY.resolve())
    assert [item["id"] for item in manifest["figures"]] == list(FIGURES)

    for name, metric_columns in FIGURES.items():
        csv_path = first / f"{name}.csv"
        csv_bytes = csv_path.read_bytes()
        csv_hash = hashlib.sha256(csv_bytes).hexdigest()
        with csv_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert rows
        assert tuple(rows[0]) == IDENTITY_COLUMNS + metric_columns

        svg_root = ET.fromstring((first / f"{name}.svg").read_text(encoding="utf-8"))
        namespace = {"svg": "http://www.w3.org/2000/svg"}
        metadata = json.loads(svg_root.findtext("svg:metadata", namespaces=namespace))
        descriptions = svg_root.findall(".//svg:desc", namespace)
        plotted = svg_root.findall(".//svg:g[@class='data-point']", namespace)
        assert metadata["csv"] == f"{name}.csv"
        assert metadata["csv_sha256"] == csv_hash
        assert metadata["point_count"] == len(rows)
        assert len(plotted) == len(rows)
        assert [int(group.attrib["data-row"]) for group in plotted] == list(
            range(len(rows))
        )
        assert any("runs=" in (description.text or "") for description in descriptions)
        if name.startswith("quality-"):
            keys = svg_root.findall(".//svg:text[@class='config-key']", namespace)
            assert len(keys) == len(rows)
            assert all(group.findall("svg:text[@class='point-id']", namespace) for group in plotted)

        png_metadata = _png_text(first / f"{name}.png")
        assert png_metadata["CSV"] == f"{name}.csv"
        assert png_metadata["CSV-SHA256"] == csv_hash
        provenance = json.loads(png_metadata["Provenance"])
        assert provenance == metadata["provenance"]

    quality_rows = list(
        csv.DictReader((first / "quality-vs-time.csv").open(encoding="utf-8"))
    )
    grouped = next(
        row
        for row in quality_rows
        if row["template_version"] == "v1.0.0"
        and row["model"] == "claude-opus-4-8"
        and row["effort"] == "high"
        and row["arm"] == "guardrails"
    )
    assert grouped == {
        "template_version": "v1.0.0",
        "provider": "claude",
        "model": "claude-opus-4-8",
        "effort": "high",
        "app": "ledger",
        "variant": "baseline",
        "phase": "build",
        "arm": "guardrails",
        "runs": "2",
        "seeds": "3|4",
        "probe_pass_rate": "0.9",
        "judge_primary_rate": "1",
        "wall_time_seconds": "750",
    }
    grouped_index = quality_rows.index(grouped)
    svg_root = ET.fromstring(
        (first / "quality-vs-time.svg").read_text(encoding="utf-8")
    )
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    group = svg_root.find(
        f".//svg:g[@class='data-point'][@data-row='{grouped_index}']", namespace
    )
    assert group is not None
    probe = group.find("svg:circle[@data-y-metric='probe_pass_rate']", namespace)
    assert probe is not None
    assert probe.attrib["data-x-value"] == "750"
    assert probe.attrib["data-y-value"] == "0.9"
    assert abs(float(probe.attrib["cx"]) - 594.70) < 0.01
    assert abs(float(probe.attrib["cy"]) - 291.0) < 0.01
    width, _, pixels = _png_pixels(first / "quality-vs-time.png")
    x, y = round(float(probe.attrib["cx"])), round(float(probe.attrib["cy"]))
    assert pixels[(y * width + x) * 3 : (y * width + x + 1) * 3] == bytes(
        (22, 125, 160)
    )

    action_rows = list(
        csv.DictReader((first / "effort-actions.csv").open(encoding="utf-8"))
    )
    action_svg = ET.fromstring(
        (first / "effort-actions.svg").read_text(encoding="utf-8")
    )
    first_action = action_svg.find(
        ".//svg:g[@class='data-point'][@data-row='0']"
        "/svg:rect[@data-metric='tool_calls']",
        namespace,
    )
    assert first_action is not None
    assert action_rows[0]["tool_calls"] == first_action.attrib["data-value"] == "40.5"
    assert abs(float(first_action.attrib["width"]) - 690.88) < 0.01


def test_export_cli_handles_missing_registry_without_creating_output(
    tmp_path: Path,
) -> None:
    output = tmp_path / "figures"
    completed = subprocess.run(
        (
            sys.executable,
            str(FIGURE_COMMAND),
            "--registry",
            str(tmp_path / "missing.jsonl"),
            "--output-dir",
            str(output),
        ),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "No benchmark runs found" in completed.stdout
    assert not output.exists()


def test_export_cli_keeps_full_set_when_a_metric_is_unavailable(tmp_path: Path) -> None:
    registry = tmp_path / "partial.jsonl"
    source = json.loads(FIXTURE_REGISTRY.read_text(encoding="utf-8").splitlines()[0])
    source["cost_usd"] = None
    registry.write_text(json.dumps(source) + "\n", encoding="utf-8")
    output = tmp_path / "figures"

    completed = subprocess.run(
        (
            sys.executable,
            str(FIGURE_COMMAND),
            "--registry",
            str(registry),
            "--output-dir",
            str(output),
        ),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    with (output / "quality-vs-cost.csv").open(encoding="utf-8") as handle:
        assert list(csv.DictReader(handle)) == []
    svg_root = ET.fromstring(
        (output / "quality-vs-cost.svg").read_text(encoding="utf-8")
    )
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    metadata = json.loads(svg_root.findtext("svg:metadata", namespaces=namespace))
    assert metadata["point_count"] == 0
    assert svg_root.findall(".//svg:g[@class='data-point']", namespace) == []


def test_effort_figures_grow_to_keep_large_cross_product_visible(tmp_path: Path) -> None:
    registry = tmp_path / "large.jsonl"
    source = json.loads(FIXTURE_REGISTRY.read_text(encoding="utf-8").splitlines()[0])
    rows = []
    for index in range(12):
        row = dict(source)
        row["run_id"] = f"large-{index}"
        row["effort"] = f"effort-{index:02d}"
        rows.append(row)
    registry.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    output = tmp_path / "figures"

    completed = subprocess.run(
        (
            sys.executable,
            str(FIGURE_COMMAND),
            "--registry",
            str(registry),
            "--output-dir",
            str(output),
        ),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    svg_root = ET.fromstring(
        (output / "effort-actions.svg").read_text(encoding="utf-8")
    )
    svg_height = int(svg_root.attrib["height"])
    png_width, png_height, _ = _png_pixels(output / "effort-actions.png")
    assert svg_height == png_height > 1200
    assert png_width == 1600
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    points = svg_root.findall(".//svg:g[@class='data-point']", namespace)
    assert len(points) == 12
    last_bar = points[-1].find("svg:rect[@data-metric='turns']", namespace)
    assert last_bar is not None
    assert float(last_bar.attrib["y"]) + float(last_bar.attrib["height"]) < svg_height - 120


def test_publication_inventory_is_registered_and_names_every_figure() -> None:
    inventory = (REPO_ROOT / "benchmarks" / "FIGURES.md").read_text(encoding="utf-8")
    benchmark_readme = (REPO_ROOT / "benchmarks" / "README.md").read_text(
        encoding="utf-8"
    )
    root_readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    for figure in FIGURES:
        assert f"`{figure}`" in inventory
    assert "Registry query" in inventory
    assert "[figure inventory](FIGURES.md)" in benchmark_readme
    assert "just bench-figures" in benchmark_readme
    assert "just bench-figures" in root_readme


def test_figure_export_imports_without_provider_or_rendering_sdk() -> None:
    completed = subprocess.run(
        (
            sys.executable,
            "-c",
            "import benchmarks.figures; import sys; "
            "assert 'headless_llm' not in sys.modules; "
            "assert 'matplotlib' not in sys.modules; assert 'PIL' not in sys.modules",
        ),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
