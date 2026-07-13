"""Blind pairwise LLM judging with explicit bias controls.

Controls, each of which is testable:

- the judge is never told that a template, a baseline, or this pack exists —
  only "two candidate implementations of the same specification";
- candidates are labeled A/B; the seed decides the first assignment and every
  panel member judges **both** presentation orders, so position bias is both
  cancelled and measured (a judge that flips with the order is reported);
- the rubric explicitly forbids rewarding volume, file count, or apparent
  effort, and demands citations from the shown files;
- the panel should span model families other than the builder's, which the
  default configuration does; the report states the panel composition.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
import random
import re

from benchmarks.e2e.agents import AgentOutcome, AgentRunner
from benchmarks.e2e.config import JudgeSettings, matches_exclude

DIMENSIONS = (
    "spec_fidelity",
    "domain_and_invariants",
    "error_handling",
    "test_quality",
    "readability_simplicity",
    "change_safety",
)

# Matched against every path component including the file name itself, so
# analyzer droppings (coverage data, OS metadata) can never leak into a
# bundle even when a gate writes them into the workspace root.
_HARD_EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".hypothesis",
    ".import_linter_cache",
    "node_modules",
    "htmlcov",
    ".coverage",
    "coverage.xml",
    "coverage.json",
    ".DS_Store",
}

_CANDIDATE_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [*DIMENSIONS, "top_risk"],
    "properties": {
        **{
            dimension: {"type": "integer", "minimum": 0, "maximum": 10}
            for dimension in DIMENSIONS
        },
        "top_risk": {"type": "string"},
    },
}

JUDGE_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "candidate_a",
        "candidate_b",
        "preference",
        "preference_strength",
        "rationale",
    ],
    "properties": {
        "candidate_a": _CANDIDATE_SCHEMA,
        "candidate_b": _CANDIDATE_SCHEMA,
        "preference": {"type": "string", "enum": ["a", "b", "tie"]},
        "preference_strength": {"type": "string", "enum": ["slight", "clear", "decisive"]},
        "rationale": {"type": "string"},
    },
}

_RUBRIC = """\
You are an independent senior Python engineer hired to arbitrate between two
candidate implementations of the same specification. Both were produced under
identical conditions. You know nothing else about their origin, and you must
not assume either one is a reference solution.

Score each candidate from 0 (unacceptable) to 10 (exemplary) on:

- spec_fidelity: does the code visibly implement the specified behavior,
  including edge cases and exact output/exit-code contracts?
- domain_and_invariants: are business rules modeled so that invalid states are
  hard to represent, with validation where data enters the system?
- error_handling: are failures detected early, reported precisely, and
  translated at boundaries without being swallowed?
- test_quality: do the tests assert meaningful behavior and edge cases?
  Judge assertion strength and case selection, not test count.
- readability_simplicity: value delivered per unit of complexity. Extra
  layers, files, or abstractions count against a candidate unless they visibly
  pay off; terseness counts against only where it hides intent.
- change_safety: how safely a newcomer can extend or modify the application
  (cohesion, coupling, dependency direction, injection points, discoverability).

Rules:

- Judge only what is shown. Do not reward volume, file count, or apparent
  effort; a smaller solution that does the same job safely scores higher on
  readability_simplicity.
- Ignore references to build, CI, documentation, or diagram tooling whose
  files are not shown; do not score infrastructure you cannot see, for or
  against either candidate.
- Cite concrete file names from the candidates in your rationale.
- Declare a preference only for the candidate you would rather maintain for
  the next year; use "tie" when the difference is within noise.
"""


class JudgingError(RuntimeError):
    """The judging bundle or a judge response is unusable."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Bundle:
    """Deterministic flattened view of one candidate's judged files."""

    text: str
    file_count: int
    total_chars: int
    truncated_files: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Judgment:
    judge: str
    order_index: int
    assignment: dict[str, str]
    outcome: AgentOutcome
    scores: dict[str, dict[str, int]]
    top_risks: dict[str, str]
    preference_arm: str
    preference_strength: str
    rationale: str

    def as_dict(self) -> dict[str, object]:
        return {
            "judge": self.judge,
            "order_index": self.order_index,
            "assignment": self.assignment,
            "scores": self.scores,
            "top_risks": self.top_risks,
            "preference_arm": self.preference_arm,
            "preference_strength": self.preference_strength,
            "rationale": self.rationale,
            "usage": self.outcome.as_dict() | {"text": ""},
        }


def _is_hard_excluded(relative: Path) -> bool:
    return any(part in _HARD_EXCLUDED_DIRS for part in relative.parts)


def redact_text(text: str, redact: tuple[str, ...]) -> str:
    """Blank out provenance literals (case-insensitive) before judging.

    Redaction is deliberately symmetric and content-preserving in shape: the
    judge sees that *something* was masked, never what. This is the standard
    blinded-review trade-off — a small amount of information is destroyed to
    keep the origin of the candidates unknowable.
    """
    for literal in redact:
        if literal.strip():
            text = re.sub(re.escape(literal), "▮▮▮", text, flags=re.IGNORECASE)
    return text


def bundle_workspace(
    workspace: Path,
    settings: JudgeSettings,
    changed_files: frozenset[str] | None = None,
) -> Bundle:
    """Flatten the judged files of one workspace into a deterministic text block.

    *changed_files* (workspace-relative POSIX paths) lists what the builder
    itself created or modified; those files bypass the exclusion patterns so
    agent-authored work is never hidden — exclusions only remove pristine
    scaffolding. Hard excludes (VCS, caches, virtualenvs) always apply.
    """
    pieces: list[str] = []
    truncated: list[str] = []
    count = 0
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(workspace)
        if _is_hard_excluded(relative):
            continue
        relative_posix = relative.as_posix()
        authored = changed_files is not None and relative_posix in changed_files
        if not authored and matches_exclude(relative_posix, settings.exclude):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        content = redact_text(content, settings.redact)
        if len(content) > settings.max_file_chars:
            content = content[: settings.max_file_chars] + "\n[... truncated for length ...]\n"
            truncated.append(relative_posix)
        pieces.append(f"--- file: {relative_posix} ---\n{content}")
        count += 1
    text = "\n".join(pieces)
    return Bundle(
        text=text,
        file_count=count,
        total_chars=len(text),
        truncated_files=tuple(truncated),
    )


def judge_prompt(spec_text: str, bundle_a: str, bundle_b: str) -> str:
    return (
        f"{_RUBRIC}\n"
        "## The specification both candidates received\n\n"
        f"{spec_text.strip()}\n\n"
        "## Candidate A\n\n"
        f"{bundle_a}\n\n"
        "## Candidate B\n\n"
        f"{bundle_b}\n\n"
        "Respond with the JSON object described by the response schema."
    )


def judge_prompt_static_text() -> str:
    """The judge-visible framing with candidate content removed, for bias tests."""
    return judge_prompt("", "", "")


def _to_plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _to_plain(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_to_plain(item) for item in value]
    return value


def _candidate_scores(raw: object, *, label: str) -> tuple[dict[str, int], str]:
    if not isinstance(raw, dict):
        raise JudgingError(f"judge response is missing candidate_{label} scores")
    scores: dict[str, int] = {}
    for dimension in DIMENSIONS:
        value = raw.get(dimension)
        if isinstance(value, bool) or not isinstance(value, int):
            raise JudgingError(f"candidate_{label}.{dimension} is not an integer")
        scores[dimension] = value
    risk = raw.get("top_risk")
    return scores, risk if isinstance(risk, str) else ""


def parse_judgment(
    outcome: AgentOutcome,
    *,
    judge: str,
    order_index: int,
    assignment: dict[str, str],
) -> Judgment:
    raw = _to_plain(outcome.structured)
    if not isinstance(raw, dict):
        raise JudgingError(f"judge {judge} returned no structured output")
    scores_a, risk_a = _candidate_scores(raw.get("candidate_a"), label="a")
    scores_b, risk_b = _candidate_scores(raw.get("candidate_b"), label="b")
    preference = raw.get("preference")
    if preference not in ("a", "b", "tie"):
        raise JudgingError(f"judge {judge} returned invalid preference {preference!r}")
    strength = raw.get("preference_strength")
    rationale = raw.get("rationale")
    return Judgment(
        judge=judge,
        order_index=order_index,
        assignment=dict(assignment),
        outcome=outcome,
        scores={assignment["a"]: scores_a, assignment["b"]: scores_b},
        top_risks={assignment["a"]: risk_a, assignment["b"]: risk_b},
        preference_arm=assignment[preference] if preference != "tie" else "tie",
        preference_strength=strength if isinstance(strength, str) else "slight",
        rationale=rationale if isinstance(rationale, str) else "",
    )


def assignments_for_seed(arms: tuple[str, str], seed: int) -> tuple[dict[str, str], dict[str, str]]:
    """Two label assignments (both orders); the seed picks which comes first."""
    first, second = arms if random.Random(seed).random() < 0.5 else (arms[1], arms[0])
    return {"a": first, "b": second}, {"a": second, "b": first}


def run_panel(
    *,
    spec_text: str,
    bundles: dict[str, Bundle],
    settings: JudgeSettings,
    seed: int,
    runners: dict[str, AgentRunner],
    working_directory: str | None = None,
    on_judgment: Callable[[Judgment], None] | None = None,
    on_failure: Callable[[dict[str, object]], None] | None = None,
) -> tuple[list[Judgment], list[dict[str, object]]]:
    """Run every panel member on both orders; collect judgments and failures.

    *working_directory* should be a neutral, empty directory: judge CLIs
    ingest instruction files (AGENTS.md/CLAUDE.md) from their working
    directory and reveal its path to the model, so inheriting the harness
    process CWD would unblind every judge. The optional observers fire as
    each verdict lands so a live front-end can reveal them one by one.
    """
    arms = tuple(bundles)
    if len(arms) != 2:
        raise JudgingError(f"pairwise judging needs exactly two candidates, got {len(arms)}")
    combined = sum(bundle.total_chars for bundle in bundles.values())
    if combined > settings.max_bundle_chars:
        raise JudgingError(
            f"judging bundles total {combined} chars, above max_bundle_chars="
            f"{settings.max_bundle_chars}; raise the limit or extend judge.exclude"
        )
    judgments: list[Judgment] = []
    failures: list[dict[str, object]] = []
    for judge_id, runner in runners.items():
        for order_index, assignment in enumerate(assignments_for_seed((arms[0], arms[1]), seed)):
            prompt = judge_prompt(
                spec_text,
                bundles[assignment["a"]].text,
                bundles[assignment["b"]].text,
            )
            try:
                outcome = runner.run(
                    prompt,
                    working_directory=working_directory,
                    timeout_seconds=settings.timeout_seconds,
                    output_schema=JUDGE_SCHEMA,
                )
                judgment = parse_judgment(
                    outcome,
                    judge=judge_id,
                    order_index=order_index,
                    assignment=assignment,
                )
                judgments.append(judgment)
                if on_judgment is not None:
                    on_judgment(judgment)
            except Exception as error:  # noqa: BLE001 - a judge failure must not sink the run
                failure: dict[str, object] = {
                    "judge": judge_id,
                    "order_index": order_index,
                    "error": f"{type(error).__name__}: {error}",
                }
                failures.append(failure)
                if on_failure is not None:
                    on_failure(failure)
    return judgments, failures


def aggregate_judgments(judgments: list[Judgment], arms: tuple[str, str]) -> dict[str, object]:
    """Panel summary with a declared primary endpoint.

    Primary endpoint: the preference of position-consistent judges (same
    verdict in both presentation orders), one vote per judge. A judge whose
    preference flips with the order carries no preference information — its
    raw votes are kept in the secondary tally for transparency but excluded
    from the primary count. Dimension means use only paired judgments (judges
    with both orders present), so a half-failed judge cannot inject
    uncancelled position bias.
    """
    by_judge: dict[str, list[Judgment]] = {}
    for judgment in judgments:
        by_judge.setdefault(judgment.judge, []).append(judgment)
    paired = {judge: items for judge, items in by_judge.items() if len(items) >= 2}
    paired_judgments = [judgment for items in paired.values() for judgment in items]

    means: dict[str, dict[str, float]] = {arm: {} for arm in arms}
    for arm in arms:
        for dimension in DIMENSIONS:
            values = [
                judgment.scores[arm][dimension]
                for judgment in paired_judgments
                if arm in judgment.scores
            ]
            if values:
                means[arm][dimension] = round(sum(values) / len(values), 2)
    overall = {
        arm: round(sum(scores.values()) / len(scores), 2) if scores else None
        for arm, scores in means.items()
    }

    preferences: dict[str, int] = {arm: 0 for arm in arms} | {"tie": 0}
    for judgment in judgments:
        preferences[judgment.preference_arm] = preferences.get(judgment.preference_arm, 0) + 1

    position_consistency = {
        judge: len({item.preference_arm for item in items}) == 1
        for judge, items in paired.items()
    }
    primary: dict[str, int] = {arm: 0 for arm in arms} | {"tie": 0}
    for judge, items in paired.items():
        if position_consistency[judge]:
            verdict = items[0].preference_arm
            primary[verdict] = primary.get(verdict, 0) + 1

    matrix = {
        judge: {str(item.order_index): item.preference_arm for item in items}
        for judge, items in by_judge.items()
    }
    return {
        "primary_preferences": primary,
        "dimension_means": means,
        "overall_mean": overall,
        "preferences": preferences,
        "position_consistency": position_consistency,
        "preference_matrix": matrix,
        "tool_calls_total": sum(judgment.outcome.tool_calls for judgment in judgments),
        "judgment_count": len(judgments),
        "paired_judge_count": len(paired),
    }
