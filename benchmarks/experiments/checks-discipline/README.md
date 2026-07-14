# Experiment 1: checks-discipline

Status: predeclared — no campaign results inspected.

## Hypothesis

Compared with `baseline` (`agents_contract=full`), the
`checks-via-commit` (`agents_contract=hooks-first`) answer set will stop agents
from redundantly invoking individual linters and the full gate. Across the
guardrails-arm build and maintenance rows, it will reduce all five primary
metrics: tool calls, turns, total tokens, wall-clock time, and cost.

The variant is adoptable only if its overall means for all five primary metrics
are lower than baseline. Its probe pass rate, position-consistent guardrails
judge win rate, and unweighted judge-dimension mean must not decrease overall;
probe pass rate must also not decrease within either application. Otherwise the
experiment is rejected and `agents_contract=full` remains the default.

## Runs

- Matrix: [`matrix.toml`](matrix.toml).
- Template ref and revision:
  `0a779837ea3f1fb63b0616d0d0c828f26947cef4`.
- Variants: `baseline` and `checks-via-commit`.
- Applications: `ledger` and `relay`.
- Seeds: 1, 2, 3; one repetition.
- Builder: `claude:claude-opus-4-8`, effort `high`.
- Fixed judges: `codex:gpt-5.6-sol` and
  `opencode:minimax/MiniMax-M3`, both effort `high`.
- Planned cells: 12. Every cell includes bare and guardrails arms plus build
  and maintenance phases.

Cost discipline sequence:

1. `just benchmark benchmarks/config/smoke.toml`
2. `just benchmark-matrix-plan benchmarks/experiments/checks-discipline/matrix.toml`
3. `just benchmark-matrix benchmarks/experiments/checks-discipline/matrix.toml`

The paid matrix is launched once after the first two commands pass.

## Metrics

Total tokens are `input_tokens + cached_input_tokens + output_tokens +
reasoning_tokens`. Means below use guardrails-arm build and maintenance rows;
the paired bare rows remain fairness controls.

| App | Variant | Runs | Tool calls | Turns | Total tokens | Wall-clock s | Cost USD | Probe pass rate | Judge outcome |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Pending | Pending | — | — | — | — | — | — | — | — |

Actual total campaign spend: pending.

## Decision

Pending the single paid campaign. Adoption would set the `agents_contract`
default to `hooks-first`, validate the generated template, add the evidence and
run ids to `CHANGELOG.md`, and create the next annotated template release.
Rejection would leave the default unchanged and record the same evidence.

## Follow-ups

Pending results. Any provider or builder replication will be a separate
experiment rather than an extra cell added after observing this campaign.

## Limitations

This is one fixed builder configuration on one machine, with n=3 seeds per app
and variant. Cells may run concurrently, so machine and provider contention can
add noise. The results are specific to the selected builder and judge models,
prompts, application pair, and runner checkout. Provider-reported or computed
usage metrics inherit the runner's measurement limitations. With three seeds,
the experiment estimates direction and does not claim statistical significance.
