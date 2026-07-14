#!/usr/bin/env python3
"""Render the append-only benchmark registry as a standalone HTML report."""

import argparse
from collections import defaultdict
from collections.abc import Iterable
import html
import json
from pathlib import Path
import sys


DEFAULT_OUTPUT_ROOT = Path("~/.local/share/guardrails-benchmark/runs")
GROUP_FIELDS = (
    "template_version",
    "provider",
    "model",
    "effort",
    "app",
    "variant",
    "phase",
    "arm",
)
MEAN_FIELDS = (
    "probe_pass_rate",
    "judge_primary_rate",
    "judge_dimension_mean",
    "coverage_percent",
    "wall_time_seconds",
    "cost_usd",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "tool_calls",
    "turns",
    "ruff_violations_per_kloc",
    "basedpyright_errors_per_kloc",
)


class RegistryError(ValueError):
    """A registry row cannot be used to build a trustworthy report."""


def load_registry(path: Path) -> list[dict[str, object]]:
    """Read JSONL rows, reporting the exact bad line instead of a traceback."""
    if not path.is_file():
        return []
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise RegistryError(
                f"{path}:{line_number}: invalid JSON: {error.msg}"
            ) from error
        if not isinstance(row, dict):
            raise RegistryError(f"{path}:{line_number}: registry row must be an object")
        rows.append(row)
    return rows


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _mean(values: Iterable[object]) -> float | None:
    numbers = [number for value in values if (number := _number(value)) is not None]
    return sum(numbers) / len(numbers) if numbers else None


def _field(row: dict[str, object], name: str) -> object:
    if name == "template_version":
        template = row.get("template")
        return template.get("version") if isinstance(template, dict) else None
    if name == "judge_dimension_mean":
        dimensions = row.get("judge_dimension_means")
        return _mean(dimensions.values()) if isinstance(dimensions, dict) else None
    if name == "judge_primary_rate":
        endpoint = row.get("judge_primary_endpoint")
        arm = row.get("arm")
        if not isinstance(endpoint, dict) or not isinstance(arm, str):
            return None
        votes = [_number(value) for value in endpoint.values()]
        denominator = sum(vote for vote in votes if vote is not None)
        numerator = _number(endpoint.get(arm))
        return (
            numerator / denominator if numerator is not None and denominator else None
        )
    if name == "ruff_violations_per_kloc":
        densities = row.get("analyzer_densities")
        return densities.get(name) if isinstance(densities, dict) else None
    if name == "basedpyright_errors_per_kloc":
        densities = row.get("analyzer_densities")
        return densities.get(name) if isinstance(densities, dict) else None
    return row.get(name)


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Average repetitions while preserving every comparison identity field."""
    grouped: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        key = tuple(str(_field(row, field) or "unavailable") for field in GROUP_FIELDS)
        grouped[key].append(row)

    summaries: list[dict[str, object]] = []
    for key in sorted(grouped):
        members = grouped[key]
        summary: dict[str, object] = dict(zip(GROUP_FIELDS, key, strict=True))
        summary["runs"] = len(members)
        for field in MEAN_FIELDS:
            summary[field] = _mean(_field(row, field) for row in members)
        probe = _number(summary["probe_pass_rate"])
        judge = _number(summary["judge_dimension_mean"])
        quality_parts = [
            value
            for value in (
                probe * 100 if probe is not None else None,
                judge * 10 if judge is not None else None,
            )
            if value is not None
        ]
        summary["quality_score"] = (
            sum(quality_parts) / len(quality_parts) if quality_parts else None
        )
        summaries.append(summary)
    return summaries


def _format(value: object, *, percent: bool = False, dollars: bool = False) -> str:
    number = _number(value)
    if number is None:
        return "—"
    if percent:
        return f"{number * 100:.1f}%"
    if dollars:
        return f"${number:.3f}"
    return f"{number:,.2f}".rstrip("0").rstrip(".")


def _options(summaries: list[dict[str, object]], field: str) -> str:
    values = sorted({str(summary[field]) for summary in summaries})
    return "".join(
        f'<option value="{html.escape(value, quote=True)}">{html.escape(value)}</option>'
        for value in values
    )


def _comparison_rows(summaries: list[dict[str, object]]) -> str:
    rendered: list[str] = []
    for summary in summaries:
        attributes = " ".join(
            f'data-{field.replace("_", "-")}="{html.escape(str(summary[field]), quote=True)}"'
            for field in GROUP_FIELDS
        )
        coverage = _format(summary["coverage_percent"])
        if coverage != "—":
            coverage += "%"
        rendered.append(
            f"<tr {attributes}>"
            f"<td>{html.escape(str(summary['template_version']))}</td>"
            f"<td>{html.escape(str(summary['provider']))}</td>"
            f"<td>{html.escape(str(summary['model']))}</td>"
            f"<td>{html.escape(str(summary['effort']))}</td>"
            f"<td>{html.escape(str(summary['app']))}</td>"
            f"<td>{html.escape(str(summary['variant']))}</td>"
            f"<td>{html.escape(str(summary['phase']))}</td>"
            f'<td><span class="arm arm-{html.escape(str(summary["arm"]), quote=True)}">'
            f"{html.escape(str(summary['arm']))}</span></td>"
            f"<td>{summary['runs']}</td>"
            f"<td>{_format(summary['probe_pass_rate'], percent=True)}</td>"
            f"<td>{_format(summary['judge_primary_rate'], percent=True)}</td>"
            f"<td>{_format(summary['judge_dimension_mean'])}</td>"
            f"<td>{coverage}</td>"
            f"<td>{_format(summary['wall_time_seconds'])}</td>"
            f"<td>{_format(summary['cost_usd'], dollars=True)}</td>"
            f"<td>{_format(summary['input_tokens'])}</td>"
            f"<td>{_format(summary['cached_input_tokens'])}</td>"
            f"<td>{_format(summary['output_tokens'])}</td>"
            f"<td>{_format(summary['reasoning_tokens'])}</td>"
            f"<td>{_format(summary['tool_calls'])}</td>"
            f"<td>{_format(summary['turns'])}</td>"
            f"<td>{_format(summary['ruff_violations_per_kloc'])}</td>"
            f"<td>{_format(summary['basedpyright_errors_per_kloc'])}</td>"
            "</tr>"
        )
    return "".join(rendered)


def render_html(rows: list[dict[str, object]]) -> str:
    """Build a self-contained report with pre-rendered data and inline charts."""
    summaries = summarize(rows)
    payload = json.dumps(summaries, separators=(",", ":"), ensure_ascii=False).replace(
        "</", "<\\/"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Benchmark Lab — cross-run comparison</title>
<style>
:root {{ color-scheme: dark; --ink:#f2f0e8; --muted:#a8a69d; --panel:#181916;
  --line:#34362f; --accent:#d8ff65; --bare:#ff9c70; --guard:#76c7ff; }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:#0d0e0c; color:var(--ink); font:14px/1.5 ui-monospace,
  SFMono-Regular, Menlo, monospace; }}
main {{ width:min(1500px, 96vw); margin:0 auto; padding:48px 0 72px; }}
header {{ display:grid; grid-template-columns:2fr 1fr; gap:32px; align-items:end;
  border-bottom:1px solid var(--line); padding-bottom:28px; }}
.eyebrow {{ color:var(--accent); letter-spacing:.18em; text-transform:uppercase; }}
h1 {{ max-width:850px; margin:.35rem 0 0; font:600 clamp(32px,5vw,72px)/.98 system-ui;
  letter-spacing:-.045em; }}
.lede {{ color:var(--muted); max-width:55ch; margin:0; }}
.filters {{ position:sticky; top:0; z-index:2; display:grid;
  grid-template-columns:repeat(5,minmax(150px,1fr)); gap:12px; padding:18px;
  margin:28px 0; background:rgba(13,14,12,.94); border:1px solid var(--line); }}
label {{ color:var(--muted); font-size:11px; letter-spacing:.08em; text-transform:uppercase; }}
select {{ width:100%; margin-top:5px; padding:9px; color:var(--ink); background:var(--panel);
  border:1px solid var(--line); font:inherit; }}
.charts {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:14px; margin:20px 0 30px; }}
.chart {{ min-width:0; padding:16px; border:1px solid var(--line); background:var(--panel); }}
h2 {{ margin:36px 0 12px; font:600 22px system-ui; letter-spacing:-.02em; }}
h3 {{ margin:0 0 6px; font:600 15px system-ui; }}
.note,.count {{ color:var(--muted); }}
svg {{ display:block; width:100%; height:270px; margin-top:10px; overflow:visible; }}
.axis {{ stroke:#55584e; stroke-width:1 }} .grid {{ stroke:#292b26; stroke-width:1 }}
.dot {{ stroke:#0d0e0c; stroke-width:2 }} .bare {{ fill:var(--bare) }}
.guardrails {{ fill:var(--guard) }} .label {{ fill:var(--muted); font-size:10px }}
.token-input {{ fill:#d8ff65 }} .token-cache {{ fill:#967cff }} .token-output {{ fill:#ffcf70 }}
.token-reasoning {{ fill:#ff769b }} .action-tools {{ fill:#76c7ff }} .action-turns {{ fill:#ff9c70 }}
.table-wrap {{ overflow:auto; border:1px solid var(--line); }}
table {{ width:100%; border-collapse:collapse; white-space:nowrap; }}
th,td {{ padding:10px 12px; text-align:right; border-bottom:1px solid var(--line); }}
th {{ position:sticky; top:0; color:var(--muted); background:#131411; font-size:10px;
  letter-spacing:.05em; text-transform:uppercase; }}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2),th:nth-child(3),td:nth-child(3),
th:nth-child(4),td:nth-child(4),th:nth-child(5),td:nth-child(5),th:nth-child(6),td:nth-child(6),
th:nth-child(7),td:nth-child(7),th:nth-child(8),td:nth-child(8)
{{ text-align:left; }}
.arm {{ display:inline-block; padding:2px 7px; border-radius:99px; color:#0d0e0c; }}
.arm-bare {{ background:var(--bare) }} .arm-guardrails {{ background:var(--guard) }}
footer {{ color:var(--muted); border-top:1px solid var(--line); margin-top:34px; padding-top:18px; }}
@media (max-width:900px) {{ header,.charts {{ grid-template-columns:1fr }}
  .filters {{ grid-template-columns:repeat(2,1fr); position:static }} }}
</style>
</head>
<body><main>
<header><div><div class="eyebrow">Benchmark Lab / canonical data view</div>
<h1>Benchmark Lab — cross-run comparison</h1></div>
<p class="lede">Append-only evidence across Copier template versions. Filter every comparison
without losing the raw identity of the model, application, variant, or phase.</p></header>
<section class="filters" aria-label="Report filters">
<label>Template version<select data-filter="template_version"><option value="">All</option>{_options(summaries, "template_version")}</select></label>
<label>Model<select data-filter="model"><option value="">All</option>{_options(summaries, "model")}</select></label>
<label>Application<select data-filter="app"><option value="">All</option>{_options(summaries, "app")}</select></label>
<label>Variant<select data-filter="variant"><option value="">All</option>{_options(summaries, "variant")}</select></label>
<label>Phase<select data-filter="phase"><option value="">All</option>{_options(summaries, "phase")}</select></label>
</section>
<p class="count"><span id="visible-count">{len(summaries)}</span> grouped arm summaries · {len(rows)} registry rows</p>
<section class="charts">
<article class="chart"><h3>Quality vs wall-clock</h3><div class="note">Composite quality (probe + judge) against seconds</div><svg id="quality-time" role="img"></svg></article>
<article class="chart"><h3>Quality vs dollars</h3><div class="note">Composite quality (probe + judge) against USD</div><svg id="quality-cost" role="img"></svg></article>
<article class="chart"><h3>Token effort</h3><div class="note">Effort metrics · Input · Cached input · Output · Reasoning</div><svg id="token-effort" role="img"></svg></article>
<article class="chart"><h3>Agent actions</h3><div class="note">Tool calls · Turns</div><svg id="agent-actions" role="img"></svg></article>
</section>
<h2>Grouped comparisons</h2>
<div class="table-wrap"><table><thead><tr>
<th>Template version</th><th>Provider</th><th>Model</th><th>Effort</th><th>Application</th><th>Variant</th><th>Phase</th>
<th>Arm</th><th>Runs</th><th>Probe pass rate</th><th>Primary win rate</th><th>Judge dimension mean</th>
<th>Coverage %</th><th>Wall-clock s</th><th>Cost</th><th>Input tokens</th><th>Cached input tokens</th>
<th>Output tokens</th><th>Reasoning tokens</th><th>Tool calls</th><th>Turns</th>
<th>Ruff / KLOC</th><th>Type errors / KLOC</th></tr></thead><tbody>{_comparison_rows(summaries)}</tbody></table></div>
<footer>Quality is a display composite of probe pass rate and the unweighted judge dimension mean;
the underlying endpoints remain separate in the table. Token counts remain comparable only within a provider.</footer>
<script id="summary-data" type="application/json">{payload}</script>
<script>
const allRows=JSON.parse(document.getElementById('summary-data').textContent);
const filters=[...document.querySelectorAll('[data-filter]')];
const ns='http://www.w3.org/2000/svg';
function selectedRows(){{return allRows.filter(row=>filters.every(f=>!f.value||row[f.dataset.filter]===f.value));}}
function node(name,attrs={{}},text=''){{const n=document.createElementNS(ns,name);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);n.textContent=text;return n;}}
function scatter(id,rows,xKey,xLabel){{const svg=document.getElementById(id);svg.replaceChildren();
 const valid=rows.filter(r=>Number.isFinite(r[xKey])&&Number.isFinite(r.quality_score));
 const W=420,H=250,p=34; svg.setAttribute('viewBox',`0 0 ${{W}} ${{H}}`);
 svg.append(node('line',{{x1:p,y1:H-p,x2:W-p,y2:H-p,class:'axis'}}),node('line',{{x1:p,y1:p,x2:p,y2:H-p,class:'axis'}}));
 if(!valid.length){{svg.append(node('text',{{x:W/2,y:H/2,'text-anchor':'middle',class:'label'}},'No numeric data'));return;}}
 const xs=valid.map(r=>r[xKey]), max=Math.max(...xs,1), min=Math.min(...xs,0);
 for(const r of valid){{const x=p+((r[xKey]-min)/(max-min||1))*(W-p*2),y=H-p-(r.quality_score/100)*(H-p*2);
  const title=`${{r.template_version}} · ${{r.model}} · ${{r.app}} · ${{r.arm}}`;
  const c=node('circle',{{cx:x,cy:y,r:7,class:`dot ${{r.arm}}`}});c.append(node('title',{{}},title));svg.append(c);}}
 svg.append(node('text',{{x:W/2,y:H-4,'text-anchor':'middle',class:'label'}},xLabel),node('text',{{x:8,y:15,class:'label'}},'quality'));
}}
function tokenEffort(rows){{const svg=document.getElementById('token-effort');svg.replaceChildren();const W=420,H=250,p=34;svg.setAttribute('viewBox',`0 0 ${{W}} ${{H}}`);
 const parts=[['input_tokens','input'],['cached_input_tokens','cache'],['output_tokens','output'],['reasoning_tokens','reasoning']];
 const totals=rows.map(r=>({{...r,total:parts.reduce((n,[k])=>n+(r[k]||0),0)}}));
 const max=Math.max(...totals.map(r=>r.total),1),bw=(W-p*2)/Math.max(totals.length,1);
 totals.forEach((r,i)=>{{let y=H-p;parts.forEach(([key,label])=>{{const h=((r[key]||0)/max)*(H-p*2);y-=h;const bar=node('rect',{{x:p+i*bw+3,y,width:Math.max(bw-6,2),height:h,class:`token-${{label}}`}});bar.append(node('title',{{}},`${{r.model}} · ${{r.app}} · ${{r.arm}} · ${{label}}: ${{Math.round(r[key]||0)}}`));svg.append(bar);}});}});
 svg.append(node('line',{{x1:p,y1:H-p,x2:W-p,y2:H-p,class:'axis'}}),node('text',{{x:W/2,y:H-4,'text-anchor':'middle',class:'label'}},'grouped arm summaries'));
}}
function agentActions(rows){{const svg=document.getElementById('agent-actions');svg.replaceChildren();const W=420,H=250,p=34;svg.setAttribute('viewBox',`0 0 ${{W}} ${{H}}`);
 const max=Math.max(...rows.flatMap(r=>[r.tool_calls||0,r.turns||0]),1),gw=(W-p*2)/Math.max(rows.length,1),bw=Math.max((gw-8)/2,2);
 rows.forEach((r,i)=>[['tool_calls','tools'],['turns','turns']].forEach(([key,label],j)=>{{const h=((r[key]||0)/max)*(H-p*2),bar=node('rect',{{x:p+i*gw+3+j*bw,y:H-p-h,width:bw-2,height:h,class:`action-${{label}}`}});bar.append(node('title',{{}},`${{r.model}} · ${{r.app}} · ${{r.arm}} · ${{label}}: ${{r[key]||0}}`));svg.append(bar);}}));
 svg.append(node('line',{{x1:p,y1:H-p,x2:W-p,y2:H-p,class:'axis'}}),node('text',{{x:W/2,y:H-4,'text-anchor':'middle',class:'label'}},'Tool calls / turns'));
}}
function update(){{const rows=selectedRows();document.getElementById('visible-count').textContent=rows.length;
 document.querySelectorAll('tbody tr').forEach(tr=>{{tr.hidden=!filters.every(f=>{{const key=f.dataset.filter.replace(/_([a-z])/g,(_,c)=>c.toUpperCase());return !f.value||tr.dataset[key]===f.value;}});}});
 scatter('quality-time',rows,'wall_time_seconds','wall-clock seconds');scatter('quality-cost',rows,'cost_usd','cost USD');tokenEffort(rows);agentActions(rows);
}}
filters.forEach(filter=>filter.addEventListener('change',update));update();
</script>
</main></body></html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT / "registry.jsonl",
        help="append-only benchmark JSONL registry",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="HTML destination (default: bench-report.html beside the registry)",
    )
    args = parser.parse_args(argv)
    registry = args.registry.expanduser().resolve()
    output = (
        args.output.expanduser().resolve()
        if args.output is not None
        else registry.with_name("bench-report.html")
    )
    try:
        rows = load_registry(registry)
    except RegistryError as error:
        print(f"Cannot render benchmark report: {error}", file=sys.stderr)
        return 2
    if not rows:
        print(f"No benchmark runs found in {registry}; run 'just benchmark' first.")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html(rows), encoding="utf-8")
    print(f"Wrote cross-run benchmark report: {output} ({len(rows)} registry rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
