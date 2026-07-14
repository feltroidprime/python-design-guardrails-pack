# Optimization experiment protocol

Use this protocol for a hypothesis-driven change to generated-repository
policy. The append-only registry is the evidence source; a template default
changes only after the predeclared primary and guard metrics support it.

Executed records: [Experiment 1: checks-discipline](experiments/checks-discipline/README.md).

## Protocol

### Hypothesis

State one causal claim, the expected direction for every primary metric, and
the minimum acceptable guard outcome before running anything. Name the current
Copier defaults as the baseline. Do not rewrite the hypothesis after seeing the
campaign results.

### Variant

Select one named answer set from `config/variants/answers.toml`. Record its
exact Copier answers and generated effect. The baseline and experiment variant
must use the same pinned template ref; only the named answers may differ.

### Matrix campaign

Declare the campaign in a tracked TOML file. Use both real applications,
multiple distinct seeds (at least three), one fixed builder configuration, one
fixed family-disjoint judge panel, and one pinned template ref for every cell.
Run the smoke config first, then the matrix dry-run. Inspect the identities and
cell count before launching the paid matrix exactly once. Preserve the builder,
runner, machine, prompts, probes, analyzers, and concurrency settings across
variants.

### Registry report

Keep the campaign rows from the append-only registry and render them with
`just bench-report`. Primary metrics are mean tool calls, turns, total tokens
(input + cached input + output + reasoning), wall-clock seconds, and cost in
USD. Guard metrics are probe pass rate and judge outcomes, including the
position-consistent primary endpoint and diagnostic dimension means. Compare
the guardrails-arm rows between variants; bare-arm rows remain paired fairness
controls and do not measure the generated-policy change.

### Decision

Adopt only when the primary metrics are cheaper or faster overall and neither
probe pass rate nor judge outcomes degrade materially. Adoption flips the
winning question default in `copier.yml`, moves the experiment from
`[Unreleased]` into a dated changelog release entry that links the report and
every justifying run id, runs `just validate`, and creates an annotated release
tag with `just release vX.Y.Z`. Downstream repositories then receive the new
baseline with `copier update`.

Reject when the primary metrics do not improve or a guard metric degrades. Keep
the current Copier default and record the rejection, report, and justifying run
ids in the changelog. A rejected experiment does not create a template release
unless another generated-repository change independently requires one.

## Decision record template

Copy this section into `experiments/<experiment>/README.md` before launch and
complete it without deleting inconvenient results.

### Hypothesis

Predeclared causal claim, expected metric directions, guard threshold, baseline,
and named variant.

### Runs

Pinned template ref and resolved revision; builder, runner, app, seed, variant,
arm, phase, and run ids; smoke and dry-run evidence; campaign start and finish.

### Metrics

| App | Variant | Runs | Tool calls | Turns | Total tokens | Wall-clock s | Cost USD | Probe pass rate | Judge outcome |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| _app_ | _variant_ | _n_ | _mean_ | _mean_ | _mean_ | _mean_ | _mean_ | _mean_ | _primary + dimensions_ |

State how missing values were handled and report actual total campaign spend.

### Decision

`adopt` or `reject`, followed by the evidence-based rationale, the exact Copier
default consequence, changelog entry, validation result, and release tag when
adopted.

### Follow-ups

List unresolved questions and the next experiment without expanding this
experiment after results are known.

### Limitations

At minimum disclose the single builder configuration, single machine, three
seeds per app and variant, provider/model specificity, concurrency, and any
missing or provider-computed metrics. Do not claim statistical significance.
