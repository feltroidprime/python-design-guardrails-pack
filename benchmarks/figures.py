#!/usr/bin/env python3
"""Export curated, offline publication figures and their plotted CSV data."""

import argparse
import binascii
import csv
from dataclasses import dataclass
import hashlib
import html
import io
import json
from pathlib import Path
import struct
import sys
from typing import Final
import zlib

if __package__:
    from .report import DEFAULT_OUTPUT_ROOT, RegistryError, load_registry, summarize
else:
    from report import DEFAULT_OUTPUT_ROOT, RegistryError, load_registry, summarize


IDENTITY_COLUMNS: Final = (
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
COLORS: Final = {
    "ink": "#172121",
    "muted": "#596568",
    "paper": "#f4f0e7",
    "grid": "#d2cec4",
    "bare": "#e46f44",
    "guardrails": "#167da0",
    "accent": "#bada55",
    "input": "#167da0",
    "cached": "#7e67a8",
    "output": "#e46f44",
    "reasoning": "#d5a52e",
}


@dataclass(frozen=True)
class Figure:
    id: str
    title: str
    subtitle: str
    metrics: tuple[str, ...]
    kind: str


FIGURES: Final = (
    Figure(
        "quality-vs-time",
        "Quality endpoints vs wall-clock",
        "Probe pass rate and position-consistent judge win rate",
        ("probe_pass_rate", "judge_primary_rate", "wall_time_seconds"),
        "quality",
    ),
    Figure(
        "quality-vs-cost",
        "Quality endpoints vs dollar cost",
        "Probe pass rate and position-consistent judge win rate",
        ("probe_pass_rate", "judge_primary_rate", "cost_usd"),
        "quality",
    ),
    Figure(
        "effort-actions",
        "Agent action budget",
        "Native tool invocations and model response cycles",
        ("tool_calls", "turns"),
        "actions",
    ),
    Figure(
        "effort-tokens",
        "Token effort composition",
        "Input, cached input, output, and reasoning tokens",
        (
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "reasoning_tokens",
        ),
        "tokens",
    ),
)


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _number_text(value: object) -> str:
    number = _number(value)
    return "" if number is None else format(number, ".12g")


def _seed_text(value: object) -> str:
    if not isinstance(value, list):
        return ""
    return "|".join(str(seed) for seed in value)


def _figure_rows(
    summaries: list[dict[str, object]], figure: Figure
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for summary in summaries:
        if any(_number(summary.get(metric)) is None for metric in figure.metrics):
            continue
        row = {
            column: (
                _seed_text(summary.get(column))
                if column == "seeds"
                else _number_text(summary.get(column))
                if column == "runs"
                else str(summary.get(column, ""))
            )
            for column in IDENTITY_COLUMNS
        }
        row.update({metric: _number_text(summary.get(metric)) for metric in figure.metrics})
        rows.append(row)
    return rows


def _csv_bytes(rows: list[dict[str, str]], figure: Figure) -> bytes:
    stream = io.StringIO(newline="")
    columns = IDENTITY_COLUMNS + figure.metrics
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _point_caption(row: dict[str, str]) -> str:
    return (
        f"template={row['template_version']}; model={row['model']}; "
        f"effort={row['effort']}; variant={row['variant']}; arm={row['arm']}; "
        f"app={row['app']}; phase={row['phase']}; runs={row['runs']}; "
        f"seeds={row['seeds']}"
    )


def _provenance(rows: list[dict[str, str]]) -> dict[str, object]:
    return {
        "template_versions": sorted({row["template_version"] for row in rows}),
        "models": sorted({row["model"] for row in rows}),
        "efforts": sorted({row["effort"] for row in rows}),
        "variants": sorted({row["variant"] for row in rows}),
        "points": [
            {
                "row": index,
                "template_version": row["template_version"],
                "model": row["model"],
                "effort": row["effort"],
                "variant": row["variant"],
                "arm": row["arm"],
                "runs": int(row["runs"]),
                "seeds": [int(seed) for seed in row["seeds"].split("|") if seed],
            }
            for index, row in enumerate(rows)
        ],
    }


def _figure_height(figure: Figure, rows: list[dict[str, str]]) -> int:
    if figure.kind == "quality":
        return max(1000, 850 + ((len(rows) + 1) // 2) * 30 + 140)
    return max(1000, 222 + len(rows) * 88 + 220)


def _legend_items(figure: Figure) -> tuple[tuple[str, str], ...]:
    if figure.kind == "quality":
        return (("bare", "bare"), ("guardrails", "guardrails"))
    if figure.kind == "actions":
        return (("guardrails", "tool calls"), ("bare", "turns"))
    return (
        ("input", "input"),
        ("cached", "cached input"),
        ("output", "output"),
        ("reasoning", "reasoning"),
    )


def _xml(value: object) -> str:
    return html.escape(str(value), quote=True)


def _svg_header(
    figure: Figure,
    rows: list[dict[str, str]],
    csv_name: str,
    csv_hash: str,
    height: int,
) -> list[str]:
    provenance = _provenance(rows)
    metadata = {
        "csv": csv_name,
        "csv_sha256": csv_hash,
        "point_count": len(rows),
        "provenance": provenance,
    }
    versions = ", ".join(provenance["template_versions"])
    models = ", ".join(provenance["models"])
    variants = ", ".join(provenance["variants"])
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="{height}" '
        f'viewBox="0 0 1600 {height}" role="img">',
        f"<metadata>{_xml(json.dumps(metadata, sort_keys=True, separators=(',', ':')))}</metadata>",
        f"<title>{_xml(figure.title)}</title>",
        f"<desc>{_xml(figure.subtitle)}. Templates: {versions}. Models: {models}. "
        f"Variants: {variants}. Every mark records runs and seeds in its description.</desc>",
        f'<rect width="1600" height="{height}" fill="{COLORS["paper"]}"/>',
        f'<rect width="1600" height="18" fill="{COLORS["accent"]}"/>',
        f'<text x="88" y="104" fill="{COLORS["ink"]}" font-family="Arial,Helvetica,sans-serif" '
        f'font-size="58" font-weight="700">{_xml(figure.title)}</text>',
        f'<text x="90" y="151" fill="{COLORS["muted"]}" font-family="Arial,Helvetica,sans-serif" '
        f'font-size="24">{_xml(figure.subtitle)}</text>',
    ]


def _scale(value: float, maximum: float, start: float, length: float) -> float:
    return start + (value / maximum if maximum else 0.0) * length


def _quality_svg(figure: Figure, rows: list[dict[str, str]]) -> list[str]:
    x_metric = figure.metrics[-1]
    x_max = max((float(row[x_metric]) for row in rows), default=1.0) * 1.08 or 1.0
    panels = (
        ("probe_pass_rate", "PROBE PASS RATE"),
        ("judge_primary_rate", "JUDGE PRIMARY WIN RATE"),
    )
    parts: list[str] = []
    geometry: list[tuple[str, int, int, int, int]] = []
    for panel_index, (metric, label) in enumerate(panels):
        left = 90 + panel_index * 755
        top, width, height = 238, 665, 530
        geometry.append((metric, left, top, width, height))
        parts.append(
            f'<text x="{left}" y="214" fill="{COLORS["ink"]}" '
            f'font-family="Arial,Helvetica,sans-serif" font-size="22" font-weight="700">{label}</text>'
        )
        for tick in range(6):
            y = top + height - tick * height / 5
            parts.append(
                f'<line x1="{left}" y1="{y:.2f}" x2="{left + width}" y2="{y:.2f}" '
                f'stroke="{COLORS["grid"]}" stroke-width="1"/>'
            )
            parts.append(
                f'<text x="{left - 14}" y="{y + 7:.2f}" text-anchor="end" '
                f'fill="{COLORS["muted"]}" font-family="Arial,Helvetica,sans-serif" '
                f'font-size="17">{tick * 20}%</text>'
            )
            x = left + tick * width / 5
            x_value = x_max * tick / 5
            x_label = (
                f"${x_value:.1f}"
                if x_metric == "cost_usd"
                else f"{x_value:,.0f}"
            )
            parts.append(
                f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + height}" '
                f'stroke="{COLORS["grid"]}" stroke-width="1"/>'
            )
            parts.append(
                f'<text x="{x:.2f}" y="{top + height + 28}" text-anchor="middle" '
                f'fill="{COLORS["muted"]}" font-family="Arial,Helvetica,sans-serif" '
                f'font-size="15">{x_label}</text>'
            )
        parts.extend(
            (
                f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + height}" '
                f'stroke="{COLORS["ink"]}" stroke-width="2"/>',
                f'<line x1="{left}" y1="{top + height}" x2="{left + width}" y2="{top + height}" '
                f'stroke="{COLORS["ink"]}" stroke-width="2"/>',
            )
        )
        unit = "WALL-CLOCK SECONDS" if x_metric == "wall_time_seconds" else "COST (USD)"
        parts.append(
            f'<text x="{left + width / 2:.2f}" y="814" text-anchor="middle" '
            f'fill="{COLORS["muted"]}" font-family="Arial,Helvetica,sans-serif" '
            f'font-size="18">{unit}</text>'
        )
    for index, row in enumerate(rows):
        marks = []
        for metric, left, top, width, height in geometry:
            x = _scale(float(row[x_metric]), x_max, left, width)
            y = top + height - float(row[metric]) * height
            color = COLORS.get(row["arm"], COLORS["muted"])
            marks.append(
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="13" fill="{color}" '
                f'stroke="{COLORS["paper"]}" stroke-width="4" '
                f'data-x-metric="{x_metric}" data-x-value="{row[x_metric]}" '
                f'data-y-metric="{metric}" data-y-value="{row[metric]}"/>'
            )
            marks.append(
                f'<text class="point-id" x="{x + 18:.2f}" y="{y - 14:.2f}" '
                f'fill="{COLORS["ink"]}" font-family="Arial,Helvetica,sans-serif" '
                f'font-size="15" font-weight="700">{index + 1}</text>'
            )
        parts.append(
            f'<g class="data-point" data-row="{index}"><desc>{_xml(_point_caption(row))}</desc>'
            + "".join(marks)
            + "</g>"
        )
    for index, row in enumerate(rows):
        column = index % 2
        line = index // 2
        parts.append(
            f'<text class="config-key" x="{90 + column * 755}" y="{850 + line * 30}" '
            f'fill="{COLORS["muted"]}" font-family="Arial,Helvetica,sans-serif" '
            f'font-size="14"><tspan font-weight="700">{index + 1}</tspan> '
            f'{_xml(_label(row))}</text>'
        )
    return parts


def _label(row: dict[str, str]) -> str:
    return (
        f"{row['template_version']} · {row['model']} · {row['arm']} · "
        f"{row['effort']} · {row['variant']}"
    )


def _visible_label_lines(row: dict[str, str]) -> tuple[str, str]:
    return (
        f"{row['template_version']} · {row['variant']} · {row['arm']}",
        f"{row['model']} · {row['effort']}",
    )


def _effort_svg(figure: Figure, rows: list[dict[str, str]]) -> list[str]:
    parts: list[str] = []
    chart_left, chart_top, chart_width, row_height = 600, 222, 870, 88
    if figure.kind == "actions":
        maximum = max(
            (float(row[metric]) for row in rows for metric in figure.metrics),
            default=1.0,
        ) or 1
        palette = (COLORS["guardrails"], COLORS["bare"])
    else:
        maximum = max(
            (sum(float(row[metric]) for metric in figure.metrics) for row in rows),
            default=1.0,
        ) or 1
        palette = (
            COLORS["input"],
            COLORS["cached"],
            COLORS["output"],
            COLORS["reasoning"],
        )
    for index, row in enumerate(rows):
        y = chart_top + index * row_height
        first_line, second_line = _visible_label_lines(row)
        parts.append(
            f'<g class="data-point" data-row="{index}"><desc>{_xml(_point_caption(row))}</desc>'
            f'<text class="config-label" x="90" y="{y + 21}" fill="{COLORS["ink"]}" '
            f'font-family="Arial,Helvetica,sans-serif" font-size="14">'
            f'<tspan x="90">{_xml(first_line)}</tspan>'
            f'<tspan x="90" dy="22">{_xml(second_line)}</tspan></text>'
        )
        if figure.kind == "actions":
            for metric_index, metric in enumerate(figure.metrics):
                width = float(row[metric]) / maximum * chart_width
                bar_y = y + 4 + metric_index * 31
                parts.append(
                    f'<rect x="{chart_left}" y="{bar_y}" width="{width:.2f}" height="23" '
                    f'fill="{palette[metric_index]}" data-metric="{metric}" '
                    f'data-value="{row[metric]}"/><text x="{chart_left + width + 10:.2f}" '
                    f'y="{bar_y + 17}" fill="{COLORS["muted"]}" '
                    f'font-family="Arial,Helvetica,sans-serif" font-size="15">'
                    f'{_xml(metric.replace("_", " "))} {row[metric]}</text>'
                )
        else:
            x = chart_left
            for metric_index, metric in enumerate(figure.metrics):
                width = float(row[metric]) / maximum * chart_width
                parts.append(
                    f'<rect x="{x:.2f}" y="{y + 13}" width="{width:.2f}" height="42" '
                    f'fill="{palette[metric_index]}" data-metric="{metric}" '
                    f'data-value="{row[metric]}"/>'
                )
                x += width
            total = sum(float(row[metric]) for metric in figure.metrics)
            parts.append(
                f'<text x="{x + 10:.2f}" y="{y + 41}" fill="{COLORS["muted"]}" '
                f'font-family="Arial,Helvetica,sans-serif" font-size="15">{total:,.0f}</text>'
            )
        parts.append("</g>")
    return parts


def _svg_bytes(
    figure: Figure,
    rows: list[dict[str, str]],
    csv_name: str,
    csv_hash: str,
) -> bytes:
    height = _figure_height(figure, rows)
    parts = _svg_header(figure, rows, csv_name, csv_hash, height)
    parts.extend(
        _quality_svg(figure, rows)
        if figure.kind == "quality"
        else _effort_svg(figure, rows)
    )
    legend = (
        "Each mark: template · model · effort · variant · arm. "
        "Runs and seed IDs are embedded per mark; CSV hash anchors the plotted data."
    )
    legend_items = _legend_items(figure)
    legend_y = height - 125
    caption_y = height - 62
    legend_x = 90
    for color_key, label in legend_items:
        parts.append(
            f'<rect x="{legend_x}" y="{legend_y}" width="18" height="18" rx="3" '
            f'fill="{COLORS[color_key]}"/><text x="{legend_x + 27}" y="{legend_y + 16}" '
            f'fill="{COLORS["ink"]}" font-family="Arial,Helvetica,sans-serif" '
            f'font-size="17">{_xml(label)}</text>'
        )
        legend_x += 48 + len(label) * 10
    parts.extend(
        (
            f'<text x="90" y="{caption_y}" fill="{COLORS["muted"]}" '
            f'font-family="Arial,Helvetica,sans-serif" font-size="16">{_xml(legend)}</text>',
            f'<text x="1510" y="{caption_y}" text-anchor="end" fill="{COLORS["muted"]}" '
            f'font-family="Arial,Helvetica,sans-serif" font-size="14">CSV SHA-256 {csv_hash[:16]}…</text>',
            "</svg>",
        )
    )
    return ("\n".join(parts) + "\n").encode("utf-8")


_FONT: Final = {
    " ": ("00000",) * 7,
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    "/": ("00001", "00010", "00100", "01000", "10000", "00000", "00000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
}
_FONT.update(
    dict(
        zip(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            (
                ("01110","10001","10001","11111","10001","10001","10001"),("11110","10001","10001","11110","10001","10001","11110"),("01111","10000","10000","10000","10000","10000","01111"),("11110","10001","10001","10001","10001","10001","11110"),("11111","10000","10000","11110","10000","10000","11111"),("11111","10000","10000","11110","10000","10000","10000"),("01111","10000","10000","10111","10001","10001","01111"),("10001","10001","10001","11111","10001","10001","10001"),("11111","00100","00100","00100","00100","00100","11111"),("00111","00010","00010","00010","10010","10010","01100"),("10001","10010","10100","11000","10100","10010","10001"),("10000","10000","10000","10000","10000","10000","11111"),("10001","11011","10101","10101","10001","10001","10001"),("10001","11001","10101","10011","10001","10001","10001"),("01110","10001","10001","10001","10001","10001","01110"),("11110","10001","10001","11110","10000","10000","10000"),("01110","10001","10001","10001","10101","10010","01101"),("11110","10001","10001","11110","10100","10010","10001"),("01111","10000","10000","01110","00001","00001","11110"),("11111","00100","00100","00100","00100","00100","00100"),("10001","10001","10001","10001","10001","10001","01110"),("10001","10001","10001","10001","10001","01010","00100"),("10001","10001","10001","10101","10101","10101","01010"),("10001","10001","01010","00100","01010","10001","10001"),("10001","10001","01010","00100","00100","00100","00100"),("11111","00001","00010","00100","01000","10000","11111"),("01110","10001","10011","10101","11001","10001","01110"),("00100","01100","00100","00100","00100","00100","01110"),("01110","10001","00001","00010","00100","01000","11111"),("11110","00001","00001","01110","00001","00001","11110"),("00010","00110","01010","10010","11111","00010","00010"),("11111","10000","10000","11110","00001","00001","11110"),("01110","10000","10000","11110","10001","10001","01110"),("11111","00001","00010","00100","01000","01000","01000"),("01110","10001","10001","01110","10001","10001","01110"),("01110","10001","10001","01111","00001","00001","01110"),
            ),
            strict=True,
        )
    )
)


class _Canvas:
    def __init__(self, width: int, height: int, color: tuple[int, int, int]) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray(color * (width * height))

    def rect(self, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
        x0, y0 = max(x, 0), max(y, 0)
        x1, y1 = min(x + width, self.width), min(y + height, self.height)
        band = bytes(color) * max(x1 - x0, 0)
        for row in range(y0, y1):
            offset = (row * self.width + x0) * 3
            self.pixels[offset : offset + len(band)] = band

    def circle(self, cx: int, cy: int, radius: int, color: tuple[int, int, int]) -> None:
        for y in range(max(0, cy - radius), min(self.height, cy + radius + 1)):
            span = int(max(radius * radius - (y - cy) ** 2, 0) ** 0.5)
            self.rect(cx - span, y, span * 2 + 1, 1, color)

    def text(self, x: int, y: int, value: str, color: tuple[int, int, int], scale: int = 3) -> None:
        cursor = x
        for char in value.upper():
            glyph = _FONT.get(char, _FONT["-"])
            for gy, line in enumerate(glyph):
                for gx, bit in enumerate(line):
                    if bit == "1":
                        self.rect(cursor + gx * scale, y + gy * scale, scale, scale, color)
            cursor += 6 * scale


def _rgb(value: str) -> tuple[int, int, int]:
    return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))  # type: ignore[return-value]


def _draw_png(figure: Figure, rows: list[dict[str, str]]) -> _Canvas:
    height = _figure_height(figure, rows)
    canvas = _Canvas(1600, height, _rgb(COLORS["paper"]))
    canvas.rect(0, 0, 1600, 18, _rgb(COLORS["accent"]))
    canvas.text(88, 74, figure.title, _rgb(COLORS["ink"]), 6)
    canvas.text(90, 145, figure.subtitle, _rgb(COLORS["muted"]), 3)
    if figure.kind == "quality":
        x_metric = figure.metrics[-1]
        x_max = max((float(row[x_metric]) for row in rows), default=1.0) * 1.08 or 1
        for panel_index, metric in enumerate(("probe_pass_rate", "judge_primary_rate")):
            left, top, width, height = 90 + panel_index * 755, 238, 665, 530
            canvas.text(left, 202, metric.replace("_", " "), _rgb(COLORS["ink"]), 3)
            canvas.rect(left, top, 2, height, _rgb(COLORS["ink"]))
            canvas.rect(left, top + height, width, 2, _rgb(COLORS["ink"]))
            for tick in range(6):
                grid_y = top + tick * height // 5
                grid_x = left + tick * width // 5
                canvas.rect(left, grid_y, width, 1, _rgb(COLORS["grid"]))
                canvas.rect(grid_x, top, 1, height, _rgb(COLORS["grid"]))
                canvas.text(left - 42, grid_y - 6, str(100 - tick * 20), _rgb(COLORS["muted"]), 1)
                x_value = x_max * tick / 5
                x_label = f"{x_value:.1f}" if x_metric == "cost_usd" else f"{x_value:.0f}"
                canvas.text(grid_x - 12, top + height + 10, x_label, _rgb(COLORS["muted"]), 1)
            for index, row in enumerate(rows):
                x = int(_scale(float(row[x_metric]), x_max, left, width))
                y = int(top + height - float(row[metric]) * height)
                canvas.circle(x, y, 11, _rgb(COLORS.get(row["arm"], COLORS["muted"])))
                canvas.text(x + 15, y - 13, str(index + 1), _rgb(COLORS["ink"]), 1)
            axis_label = "COST USD" if x_metric == "cost_usd" else "WALL CLOCK SECONDS"
            canvas.text(left + 215, top + height + 30, axis_label, _rgb(COLORS["muted"]), 2)
        for index, row in enumerate(rows):
            key_x = 90 + (index % 2) * 755
            key_y = 836 + (index // 2) * 30
            canvas.text(
                key_x,
                key_y,
                f"{index + 1} {_label(row)[:72]}",
                _rgb(COLORS["muted"]),
                1,
            )
    else:
        chart_left, chart_top, chart_width, row_height = 600, 222, 870, 88
        maximum = (
            max(
                (float(row[metric]) for row in rows for metric in figure.metrics),
                default=1.0,
            )
            if figure.kind == "actions"
            else max(
                (
                    sum(float(row[metric]) for metric in figure.metrics)
                    for row in rows
                ),
                default=1.0,
            )
        ) or 1
        palette = (
            (_rgb(COLORS["guardrails"]), _rgb(COLORS["bare"]))
            if figure.kind == "actions"
            else tuple(_rgb(COLORS[key]) for key in ("input", "cached", "output", "reasoning"))
        )
        for index, row in enumerate(rows):
            y = chart_top + index * row_height
            first_line, second_line = _visible_label_lines(row)
            label_scale = 2 if max(len(first_line), len(second_line)) <= 42 else 1
            canvas.text(90, y + 7, first_line, _rgb(COLORS["ink"]), label_scale)
            canvas.text(
                90,
                y + 34,
                second_line,
                _rgb(COLORS["muted"]),
                label_scale,
            )
            if figure.kind == "actions":
                for metric_index, metric in enumerate(figure.metrics):
                    width = int(float(row[metric]) / maximum * chart_width)
                    canvas.rect(chart_left, y + metric_index * 31, width, 23, palette[metric_index])
                    canvas.text(
                        chart_left + width + 8,
                        y + metric_index * 31 + 6,
                        row[metric],
                        _rgb(COLORS["muted"]),
                        1,
                    )
            else:
                x = chart_left
                for metric_index, metric in enumerate(figure.metrics):
                    width = int(float(row[metric]) / maximum * chart_width)
                    canvas.rect(x, y + 10, width, 42, palette[metric_index])
                    x += width
                canvas.text(
                    x + 8,
                    y + 25,
                    f"{sum(float(row[metric]) for metric in figure.metrics):.0f}",
                    _rgb(COLORS["muted"]),
                    1,
                )
        canvas.text(chart_left, chart_top - 28, "0", _rgb(COLORS["muted"]), 1)
        canvas.text(
            chart_left + chart_width - 30,
            chart_top - 28,
            f"{maximum:.0f}",
            _rgb(COLORS["muted"]),
            1,
        )
    png_legend = tuple((color, label.upper()) for color, label in _legend_items(figure))
    legend_y = canvas.height - 125
    legend_x = 82
    for color_key, label in png_legend:
        canvas.rect(legend_x, legend_y, 18, 18, _rgb(COLORS[color_key]))
        canvas.text(legend_x + 28, legend_y - 1, label, _rgb(COLORS["ink"]), 2)
        legend_x += 58 + len(label) * 12
    canvas.text(
        90,
        canvas.height - 70,
        "RUN AND SEED PROVENANCE EMBEDDED PER POINT",
        _rgb(COLORS["muted"]),
        2,
    )
    return canvas


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _png_bytes(
    figure: Figure,
    rows: list[dict[str, str]],
    csv_name: str,
    csv_hash: str,
) -> bytes:
    canvas = _draw_png(figure, rows)
    raw = b"".join(
        b"\0" + bytes(canvas.pixels[offset : offset + canvas.width * 3])
        for offset in range(0, len(canvas.pixels), canvas.width * 3)
    )
    provenance = json.dumps(_provenance(rows), sort_keys=True, separators=(",", ":"))
    texts = {
        "Title": figure.title,
        "Description": figure.subtitle,
        "CSV": csv_name,
        "CSV-SHA256": csv_hash,
        "Provenance": provenance,
    }
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            _chunk(
                b"IHDR",
                struct.pack(">IIBBBBB", canvas.width, canvas.height, 8, 2, 0, 0, 0),
            ),
            *(
                _chunk(b"tEXt", key.encode("latin-1") + b"\0" + value.encode("latin-1"))
                for key, value in texts.items()
            ),
            _chunk(b"IDAT", zlib.compress(raw, 9)),
            _chunk(b"IEND", b""),
        )
    )


def export_figures(
    rows: list[dict[str, object]], output_dir: Path, source: Path
) -> list[dict[str, object]]:
    summaries = summarize(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []
    for figure in FIGURES:
        plotted = _figure_rows(summaries, figure)
        csv_name = f"{figure.id}.csv"
        csv_data = _csv_bytes(plotted, figure)
        csv_hash = hashlib.sha256(csv_data).hexdigest()
        (output_dir / csv_name).write_bytes(csv_data)
        (output_dir / f"{figure.id}.svg").write_bytes(
            _svg_bytes(figure, plotted, csv_name, csv_hash)
        )
        (output_dir / f"{figure.id}.png").write_bytes(
            _png_bytes(figure, plotted, csv_name, csv_hash)
        )
        manifest.append(
            {
                "id": figure.id,
                "csv": csv_name,
                "csv_sha256": csv_hash,
                "points": len(plotted),
            }
        )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {"schema_version": 1, "source": str(source), "figures": manifest},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT / "registry.jsonl",
        help="append-only benchmark JSONL registry",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="figure destination (default: publication-figures beside registry)",
    )
    args = parser.parse_args(argv)
    registry = args.registry.expanduser().resolve()
    output_dir = (
        args.output_dir.expanduser().resolve()
        if args.output_dir is not None
        else registry.with_name("publication-figures")
    )
    try:
        rows = load_registry(registry)
    except RegistryError as error:
        print(f"Cannot export publication figures: {error}", file=sys.stderr)
        return 2
    if not rows:
        print(f"No benchmark runs found in {registry}; run 'just benchmark-matrix' first.")
        return 0
    manifest = export_figures(rows, output_dir, registry)
    print(
        f"Exported {len(manifest)} publication figures to {output_dir} "
        f"({len(rows)} registry rows)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
