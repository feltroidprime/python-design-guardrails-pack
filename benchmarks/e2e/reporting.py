"""Render the benchmark results into an auditable Markdown report.

The report never hides a number that went against either arm: raw analyzer
outputs stay on disk next to it, and a fixed Limitations section spells out
what this benchmark cannot claim.
"""

from benchmarks.e2e.config import ARM_BARE, ARM_GUARDRAILS, ARMS
from benchmarks.e2e.judging import DIMENSIONS

_ARM_TITLES = {ARM_BARE: "Bare repo", ARM_GUARDRAILS: "Template repo"}

_LIMITATIONS = """\
- One build per arm per run: LLM builders are nondeterministic, so treat any
  single run as one sample, not a verdict. Re-run with other seeds/models
  before generalizing.
- Functional probes only cover the contract written in the specification;
  behavior outside it is judged, not executed.
- Judges cannot be fully blinded: architectural style is visible in the code
  itself. The controls (neutral framing, A/B labels, both orders, cross-family
  panel, anti-volume rubric) reduce but do not eliminate this.
- The template arm starts from generated scaffolding; its metrics measure the
  combined value of that scaffolding plus the builder's work. That combination
  is exactly what the pack sells, but attribute it accordingly.
- Static analyzers (ruff/basedpyright/radon) measure proxies of quality, not
  quality itself; they are pinned and configured identically for both arms.
- Coverage is measured in-process over the application scope (the same
  symmetric exclusions as the judge bundle). An arm whose tests drive the
  program only through subprocesses measures near zero here: read that number
  as in-process testability, together with the own-test results and the
  judge's test_quality dimension, not as absence of tests.
- Blinding is defense-in-depth, not absolute: judges run tool-less (where the
  provider allows) in a neutral empty directory, bundles are provenance-
  redacted, and observed judge tool calls are reported — but host-level agent
  configuration (global instruction files, hooks) still shapes builder and
  judge behavior identically across arms while varying across machines.
- The builder inherits the host machine's agent CLI configuration (settings,
  hooks); this is symmetric between arms but makes absolute numbers
  machine-dependent.
- Token counts are comparable only within a provider: providers use different
  tokenizers and native accounting conventions even though headless_llm keeps
  uncached input, cached input, output, and reasoning counts distinct.
- Cost provenance is explicit. `reported` means provider-supplied dollars;
  `computed` means headless_llm applied its pinned per-model pricing table.
  Computed API-equivalent cost can differ from subscription credits or
  negotiated pricing; a missing value means neither path was available.
- This design measures one greenfield build of one small application by one
  model. It cannot measure maintenance-phase value (the template's core
  claim); `change_safety` is judged from reading, not from performing changes.
"""


def _fmt(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def _get(mapping: object, *keys: str) -> object:
    current = mapping
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def _arm_row(results: dict[str, object], label: str, *keys: str) -> list[str]:
    return [label, *[_fmt(_get(results, "arms", arm, *keys)) for arm in ARMS]]


def _build_section(results: dict[str, object]) -> str:
    rows = [
        _arm_row(results, "Workspace setup (s)", "setup", "seconds"),
        _arm_row(results, "Build wall time (s)", "build", "duration_seconds"),
        _arm_row(results, "Agent turns (model response cycles)", "build", "turns"),
        _arm_row(results, "Tool calls (native invocations)", "build", "tool_calls"),
        _arm_row(results, "Input tokens (non-cached)", "build", "input_tokens"),
        _arm_row(results, "Cached input tokens (context reads)", "build", "cached_input_tokens"),
        _arm_row(results, "Output tokens", "build", "output_tokens"),
        _arm_row(results, "Reasoning tokens", "build", "reasoning_tokens"),
        _arm_row(results, "Cost (USD, cache included)", "build", "cost_usd"),
        _arm_row(results, "Cost provenance", "build", "cost_provenance"),
        _arm_row(results, "Build error", "build", "error"),
    ]
    return _table(["Build effort", *[_ARM_TITLES[arm] for arm in ARMS]], rows)


def _probe_section(results: dict[str, object]) -> str:
    names: list[str] = []
    per_arm: dict[str, dict[str, bool]] = {}
    for arm in ARMS:
        probe_results = _get(results, "arms", arm, "probes", "results")
        per_arm[arm] = {}
        if isinstance(probe_results, list):
            for entry in probe_results:
                if isinstance(entry, dict):
                    name = str(entry.get("name"))
                    if name not in names:
                        names.append(name)
                    per_arm[arm][name] = bool(entry.get("passed"))
    rows = [
        [name, *[("pass" if per_arm[arm].get(name) else "FAIL") for arm in ARMS]]
        for name in names
    ]
    rows.append(
        [
            "**pass rate**",
            *[_fmt(_get(results, "arms", arm, "probes", "pass_rate")) for arm in ARMS],
        ]
    )
    return _table(["Functional probe", *[_ARM_TITLES[arm] for arm in ARMS]], rows)


def _metrics_section(results: dict[str, object]) -> str:
    rows = [
        _arm_row(results, "`uv sync` succeeds", "metrics", "install", "succeeded"),
        _arm_row(results, "Own tests exit code", "metrics", "own_tests", "exit_code"),
        _arm_row(results, "Own tests passed", "metrics", "own_tests", "counts", "passed"),
        _arm_row(results, "Own tests failed", "metrics", "own_tests", "counts", "failed"),
        _arm_row(
            results,
            "In-process coverage of application code (%)",
            "metrics",
            "coverage",
            "percent",
        ),
        _arm_row(
            results,
            "Coverage measurement exit code (0 = ok)",
            "metrics",
            "coverage",
            "run_exit_code",
        ),
        _arm_row(results, "App source files", "metrics", "loc", "source_files"),
        _arm_row(results, "App source LOC (non-blank)", "metrics", "loc", "source_loc"),
        _arm_row(results, "App test LOC (non-blank)", "metrics", "loc", "test_loc"),
        _arm_row(
            results,
            "Whole-repo py LOC (incl. infrastructure, descriptive)",
            "metrics",
            "loc_repo",
            "source_loc",
        ),
        _arm_row(results, "Ruff violations (app scope, neutral rules)", "metrics", "ruff", "violations"),
        _arm_row(results, "Ruff violations per app KLOC", "metrics", "ruff", "per_kloc"),
        _arm_row(results, "Basedpyright errors (app scope, standard mode)", "metrics", "basedpyright", "errors"),
        _arm_row(results, "Basedpyright errors per app KLOC", "metrics", "basedpyright", "errors_per_kloc"),
        _arm_row(results, "Cyclomatic complexity (app scope, mean)", "metrics", "radon", "average_complexity"),
        _arm_row(results, "Cyclomatic complexity (app scope, max)", "metrics", "radon", "max_complexity"),
        _arm_row(results, "Complexity blocks analyzed", "metrics", "radon", "blocks"),
    ]
    table = _table(["Quantitative metric (application scope)", *[_ARM_TITLES[arm] for arm in ARMS]], rows)
    gate_lines: list[str] = []
    for arm in ARMS:
        present = _get(results, "arms", arm, "native_gate", "present")
        if present:
            passed = _get(results, "arms", arm, "native_gate", "passed")
            verdict = "passes" if passed else "FAILS"
            gate_lines.append(f"- {_ARM_TITLES[arm]}: ships its own quality gate, which {verdict}.")
        else:
            gate_lines.append(f"- {_ARM_TITLES[arm]}: no native quality gate.")
    gate_note = (
        "Arm-specific signal (not part of the cross-arm comparison):\n" + "\n".join(gate_lines)
    )
    return f"{table}\n\n{gate_note}"


def _preference_tally(tally: object) -> str:
    if not isinstance(tally, dict):
        return "—"
    return ", ".join(
        f"{_ARM_TITLES.get(str(arm), str(arm))}: {count}" for arm, count in tally.items()
    )


def _judging_section(results: dict[str, object]) -> str:
    aggregate = _get(results, "judging", "aggregate")
    if not isinstance(aggregate, dict):
        return "_No judgments were collected._"
    parts = [
        "**Primary endpoint — preference of position-consistent judges "
        "(one vote per judge; flipped judges carry no preference information):** "
        + _preference_tally(aggregate.get("primary_preferences")),
        "",
    ]

    matrix = aggregate.get("preference_matrix")
    if isinstance(matrix, dict) and matrix:
        rows = []
        consistency = aggregate.get("position_consistency")
        consistency = consistency if isinstance(consistency, dict) else {}
        for judge, orders in matrix.items():
            verdicts = orders if isinstance(orders, dict) else {}
            first = _ARM_TITLES.get(str(verdicts.get("0")), str(verdicts.get("0")))
            second = _ARM_TITLES.get(str(verdicts.get("1")), str(verdicts.get("1")))
            state = consistency.get(judge)
            status = "consistent" if state else ("FLIPPED" if state is not None else "incomplete")
            rows.append([str(judge), first, second, status])
        parts.append(_table(["Judge", "Order 1 verdict", "Order 2 verdict", "Position"], rows))
        parts.append("")

    rows = [
        [
            dimension,
            *[
                _fmt(_get(aggregate, "dimension_means", arm, dimension))
                for arm in ARMS
            ],
        ]
        for dimension in DIMENSIONS
    ]
    rows.append(
        ["**unweighted mean (diagnostic)**", *[_fmt(_get(aggregate, "overall_mean", arm)) for arm in ARMS]]
    )
    parts.extend(
        [
            _table(
                [
                    "Judge dimension (paired judgments only, 0-10)",
                    *[_ARM_TITLES[arm] for arm in ARMS],
                ],
                rows,
            ),
            "",
            "Raw vote tally including position-biased votes (transparency only): "
            + _preference_tally(aggregate.get("preferences")),
            "",
            f"Judge tool calls observed (integrity check, expected 0): "
            f"{_fmt(aggregate.get('tool_calls_total'))}",
        ]
    )
    failures = _get(results, "judging", "failures")
    if isinstance(failures, list) and failures:
        parts.append("")
        parts.append("Judge failures (excluded from aggregates):")
        parts.extend(
            f"- {failure.get('judge')}: {failure.get('error')}"
            for failure in failures
            if isinstance(failure, dict)
        )
    return "\n".join(parts)


def _meta_section(results: dict[str, object]) -> str:
    meta = _get(results, "meta")
    if not isinstance(meta, dict):
        return ""
    judges = meta.get("judges")
    judge_text = ", ".join(str(judge) for judge in judges) if isinstance(judges, list) else "—"
    template = meta.get("template")
    template = template if isinstance(template, dict) else {}
    answers = template.get("answers")
    answer_text = (
        ", ".join(f"{key}={value}" for key, value in sorted(answers.items()))
        if isinstance(answers, dict)
        else "—"
    )
    lines = [
        f"- Run: `{_fmt(meta.get('run_id'))}` started {_fmt(meta.get('started_utc'))}",
        f"- Builder: `{_fmt(meta.get('builder'))}` (same agent, same prompt for both arms)",
        f"- Judge panel: {judge_text}",
        f"- Seed: {_fmt(meta.get('seed'))}; config: `{_fmt(meta.get('config_path'))}`",
        f"- Pack revision: `{_fmt(meta.get('pack_revision'))}`; "
        f"headless_llm revision: `{_fmt(meta.get('headless_llm_revision'))}`",
        f"- Copier template: `{_fmt(template.get('version'))}` "
        f"(requested `{_fmt(template.get('vcs_ref'))}`, variant "
        f"`{_fmt(template.get('variant'))}`); answers: {answer_text}",
        f"- Analyzer pins: {_fmt(meta.get('tool_pins'))}",
    ]
    return "\n".join(lines)


def render_report(results: dict[str, object]) -> str:
    sections = [
        "# Template value benchmark — one LLM, same app, with vs. without the template",
        "",
        _meta_section(results),
        "",
        "Both arms received the **identical prompt** and agent configuration. "
        "The only difference: one repository started empty, the other started "
        "from this pack's generated template.",
        "",
        "## Build effort",
        "",
        _build_section(results),
        "",
        "## Functional acceptance (objective, scripted)",
        "",
        _probe_section(results),
        "",
        "_Probes form one stateful scenario (shared database, captured ids): "
        "a single early failure can cascade into several later rows._",
        "",
        "## Quantitative quality metrics (pinned neutral analyzers)",
        "",
        _metrics_section(results),
        "",
        "## Qualitative judgment (blind LLM panel)",
        "",
        _judging_section(results),
        "",
        "## Limitations",
        "",
        _LIMITATIONS,
    ]
    return "\n".join(sections) + "\n"
