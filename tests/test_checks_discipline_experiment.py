"""Acceptance tests for optimization experiment 1."""

from pathlib import Path

from benchmarks.e2e.matrix import load_matrix_config, plan_matrix


REPO_ROOT = Path(__file__).resolve().parents[1]
PINNED_TEMPLATE_REF = "0a779837ea3f1fb63b0616d0d0c828f26947cef4"


def test_experiment_protocol_is_registered_and_has_decision_template() -> None:
    benchmark_readme = (REPO_ROOT / "benchmarks" / "README.md").read_text(
        encoding="utf-8"
    )
    protocol = (REPO_ROOT / "benchmarks" / "EXPERIMENTS.md").read_text(
        encoding="utf-8"
    )

    assert "[optimization experiment protocol](EXPERIMENTS.md)" in benchmark_readme
    for heading in (
        "## Protocol",
        "### Hypothesis",
        "### Variant",
        "### Matrix campaign",
        "### Registry report",
        "### Decision",
        "## Decision record template",
        "### Runs",
        "### Metrics",
        "### Follow-ups",
        "### Limitations",
    ):
        assert heading in protocol
    for metric in (
        "tool calls",
        "turns",
        "total tokens",
        "wall-clock",
        "cost",
        "probe pass rate",
        "judge outcomes",
    ):
        assert metric in protocol


def test_checks_discipline_matrix_is_the_predeclared_twelve_cell_campaign() -> None:
    matrix = load_matrix_config(
        REPO_ROOT / "benchmarks" / "experiments" / "checks-discipline" / "matrix.toml",
        repo_root=REPO_ROOT,
    )

    assert tuple(app.project.name for app in matrix.apps) == ("ledger", "relay")
    assert matrix.seeds == (1, 2, 3)
    assert matrix.variants == ("baseline", "checks-via-commit")
    assert matrix.repetitions == 1
    assert len(matrix.builders) == 1
    assert matrix.builders[0].identity == "claude:claude-opus-4-8"
    assert matrix.builders[0].effort == "high"
    assert matrix.template_vcs_ref == PINNED_TEMPLATE_REF
    assert matrix.template_identity == {
        "version": PINNED_TEMPLATE_REF,
        "vcs_ref": PINNED_TEMPLATE_REF,
        "revision": PINNED_TEMPLATE_REF,
        "source_digest": None,
        "dirty": False,
    }
    assert matrix.variant_answers == {
        "baseline": {},
        "checks-via-commit": {"agents_contract": "hooks-first"},
    }
    assert len(plan_matrix(matrix)) == 12


def test_checks_discipline_hypothesis_and_decision_rule_are_predeclared() -> None:
    protocol = (REPO_ROOT / "benchmarks" / "EXPERIMENTS.md").read_text(
        encoding="utf-8"
    )
    record = (
        REPO_ROOT
        / "benchmarks"
        / "experiments"
        / "checks-discipline"
        / "README.md"
    ).read_text(encoding="utf-8")

    assert "[Experiment 1: checks-discipline](experiments/checks-discipline/README.md)" in protocol
    assert "Status: predeclared" in record
    assert "`baseline` (`agents_contract=full`)" in record
    assert "`checks-via-commit` (`agents_contract=hooks-first`)" in record
    assert "all five primary metrics" in record
    assert "must not decrease" in record
    assert PINNED_TEMPLATE_REF in record
