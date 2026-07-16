# Python Design Guardrails Pack

Generated repositories include an agent-native CLI contract: one closed
command catalog drives help and machine-readable capabilities, while an
independent typed case set must cover every command at the detached process
seam. JSON envelopes, exit classes, bounds, continuations, and retry policy are
versioned in generated ADR-0003.

## Ship Python faster without letting the codebase rot

Generate an opinionated Python 3.14 repository where architecture, typing, tests, documentation, diagrams, coding-agent behavior, hooks, and CI agree from the first commit.

You keep the product decisions. The repository automates the rules a machine can verify, so structural shortcuts fail now instead of becoming expensive archaeology later.

**Move fast today. Stay changeable tomorrow.**

## The expensive part starts after “it works”

A blank repository feels fast. Then the deadline arrives.

Time and UUID calls leak into domain logic. Database details cross boundaries. `utils.py` becomes a junk drawer. Tests certify mocks instead of real adapters. The diagram stops matching the code.

Coding agents amplify the same failure mode. Without a shared contract, they create parallel abstractions, hidden dependencies, optional-state sprawl, and confident inconsistency.

Nothing necessarily breaks that day. That is what makes the drift dangerous.

The bill arrives on the next feature:

- a small change touches unrelated modules;
- nobody knows which layer owns a decision;
- every review repeats the same design arguments;
- stale documentation misleads humans and agents;
- refactoring feels unsafe because boundaries and tests disagree.

You lose time building the foundations, then lose it again repairing the drift those missing foundations allowed.

## The repository remembers, so you do not have to

This pack turns design intent into an executable repository contract.

Humans and coding agents follow the same rules. Reference implementations show the intended seams. One gate enforces the contract locally, before push, and in CI.

The payoff is direct: less setup, less review churn, faster safe changes, and a codebase that remains legible after its original authors leave.

## Start a repository

Requires Python 3.14, [`uv`](https://docs.astral.sh/uv/), [`just`](https://github.com/casey/just), and [`bun`](https://bun.sh). Install [`gh`](https://cli.github.com/) for automatic GitHub repository creation or the opt-in private session profiler; standard bootstrap, checks, and generated CI do not resolve that private package.

```bash
just install
python-repo init my-product .
cd my-product
just bootstrap
```

`python-repo init` creates the project, initializes Git on `main`, commits the baseline, and pushes a private GitHub repository. Use `--public`, `--no-github`, `--no-git`, or `--package NAME` as needed.

If GitHub creation fails, the local repository remains intact and the CLI prints the recovery command. Run `python-repo init --help` for the complete interface.

Generated repositories retain the pack's durable GitHub provenance. From a
clean branch, `just scaffold-update` applies the newest tagged pack release
through Copier's three-way merge; `just update` remains dependency-only.

Repositories generated before `scaffold-update` existed can bootstrap it by
running the recipe body once from a clean branch:

```bash
env -u PYTHONPYCACHEPREFIX uvx --from copier==9.17.0 copier update --defaults --conflict inline
```

That command can only follow a reachable tagged Git source. If the older
`.copier-answers.yml` records a temporary or installed local `_src_path`, first
replace only that value with
`https://github.com/feltroidprime/python-design-guardrails-pack.git` on the
clean migration branch. The update then records the durable source and adds
`just scaffold-update`; Copier owns the answers file again after this one-time
provenance repair.

## Features that change the outcome

One opinionated stack. One reason for every choice.

| Choice | Value |
|---|---|
| Installable `python-repo` CLI | Replace copy-and-clean setup with one stable command. |
| Pinned Copier engine | Use maintained generation with controlled renderer behavior. |
| Validated answers and strict Jinja | Reject bad package names, unknown data, and half-rendered output immediately. |
| Copier provenance and `just scaffold-update` | Pull tagged template releases with a three-way merge instead of blindly replacing local changes. |
| Automatic Git and optional GitHub setup | Start from a committed baseline and publish without manual remote wiring. |
| Python 3.14 only | Use current typing and language semantics without compatibility branches. |
| No third-party runtime dependencies by default | Add only what the product needs; keep guardrails in the development group. |
| `uv`, not pip or Poetry | One tool owns Python, dependency resolution, environments, the lockfile, and builds. |
| `just`, not Make | One repair-and-verification route, plus explicit setup, diagram-viewing, and dependency-update branches. |
| `prek`, not pre-commit | Native TOML hook policy with fast commit checks and the full gate before push. |
| Ruff from the project environment | Hooks, local commands, and CI use the exact Ruff version resolved in `uv.lock`. |
| Broad Ruff policy | Enforce formatting, correctness, security, performance, modern Python, and complexity in one tool. |
| BasedPyright with warnings as errors | Reject `Any`, missing types, unsafe overrides, incomplete matches, and stale ignores. |
| One quality-gate script | Apply safe lint, format, and diagram repairs locally, then check lockfile, types, architecture, docs, imports, diagrams, tests, and coverage in order. |
| Same gate locally, pre-push, and in CI | Remove the gap between “works here” and “accepted by the repository.” |
| Ports-and-adapters layers | Enforce `bootstrap → adapters → application → domain` and independent adapter sides. |
| Framework-free synchronous domain | Keep business rules deterministic and isolated from I/O, clocks, randomness, UUIDs, and concurrency. |
| Application-owned `Protocol` ports | Make dependencies explicit and infrastructure replaceable through constructor injection. |
| Single composition root | Keep production wiring visible and prevent hidden service location. |
| Working vertical slice | Replace the sample `Item` domain while keeping proven cross-cutting foundations. |
| Clock and ID ports | Make time and identifiers deterministic in tests. |
| Typed events with a real audit consumer | Demonstrate decoupling through a working flow, not an unused abstraction. |
| Memory and SQLite adapters | Show two interchangeable implementations behind the same port. |
| Error translation and context-managed resources | Keep infrastructure failures out of the core and lifecycle cleanup explicit. |
| Shared adapter contract tests | Prove every implementation obeys the same behavior. |
| Versioned agent-native CLI contract | Provide stable JSON, exit codes, capabilities, bounded queries, and human output without prompts or TTY assumptions. |
| Claude/Codex session evidence | Import a commit-pinned private Python module that converts complete native transcripts through Harbor 0.18.0 into ATIF-v1.7, compact TSV/route views, content-addressed blobs, and a self-checking manifest without semantic inference; opt-in E2E sampling spans five local size quantiles per agent. |
| AST architecture guard | Enforce domain purity, immutable messages, size limits, package surfaces, suppressions, and CLI boundaries. |
| None and Path discipline | Parse uncertainty and filesystem text at the edge instead of infecting the core. |
| Import Linter contracts | Make dependency direction and adapter independence build failures. |
| pytest, Hypothesis, and deterministic integration tests | Cover examples, broad invariant spaces, adapter contracts, and real local wiring. |
| Sockets disabled and 90% branch coverage floor | Block accidental live-network tests and expose untested decisions. |
| Derived LikeC4 architecture model | Generate diagrams from the same import graph the gate enforces. |
| Pinned LikeC4 through `bunx` | Get validated diagrams without `package.json`, `node_modules`, or a JavaScript lockfile. |
| Documentation map and guard | Reject broken paths, unregistered docs, malformed ADRs, numbering gaps, and dangling exceptions. |
| ADR, exception, pattern, and migration rules | Make design debt owned, scoped, revisitable, and removable. |
| Optional `AGENTS.md` plus `CLAUDE.md` bridge | Give humans and coding agents one operating contract without duplicated instructions. |
| Design-aware pull request template | Put ownership, invariants, evidence, change spread, migration, and rollback into review. |
| Reproducible value benchmark | Compare the same LLM task with and without the template across build quality, effort, and maintenance. |

Replace the `Item` domain. Keep the foundation bricks. Their rationale lives in the generated `docs/adr/0002-foundation-ports-and-reference-adapters.md`.

## Opinionated by design

This is not an empty folder or a framework starter. It chooses Python 3.14, uv, just, prek, ports and adapters, a synchronous domain, deterministic tests, and executable documentation.

No tool can prove that a name is good or an abstraction is worthwhile. Observable rules are enforced; irreducible trade-offs require an ADR; exceptions are explicit and expire.

## Measure it

`benchmarks/` gives the same LLM byte-identical tasks in a blank repository and a generated one, then compares behavior, analyzers, coverage, effort, blind judging, and later maintenance.

```bash
just benchmark              # run one two-arm experiment
just benchmark-matrix-plan  # inspect a campaign without spending
just bench-report           # build the offline comparison report
just bench-figures          # export article SVG/PNG/CSV figures
```

See `benchmarks/README.md` for methodology, variants, bias controls, and all benchmark commands.

## Maintaining this pack

This is a meta-repository: `template/` is the product, `copier.yml` owns rendering, `instantiate.py` owns the CLI, and the root `AGENTS.md` is the maintainer contract.

```bash
just test           # parallel generator tests
just validate       # canonical full validation
just release vX.Y.Z # verify and create an annotated release tag
```

`just validate` generates a throwaway repository, checks template cleanliness and rendering, resolves dependencies, runs the downstream gate, and tests an offline Copier update.

See `DESIGN_GUARDRAILS.md` for the design-to-enforcement rationale and `VALIDATION.md` for the last recorded full validation.
