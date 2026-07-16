# Integrating CLI agent-readiness into the Python template

Status: research note, 2026-07-15. This note evaluates a design; it does not
change the generated repository contract.

## Question

How should the template embody the philosophy of Every's pinned
[`cli-agent-readiness-reviewer`](https://github.com/EveryInc/compound-engineering-plugin/blob/9f023bb22d776527aa4ffbdc8af394d37c7ec331/plugins/compound-engineering/agents/review/cli-agent-readiness-reviewer.md): keep a hand-written parser, adopt Python's native `argparse`, or add a third-party CLI framework?

## What the philosophy actually requires

The referenced reviewer evaluates seven properties: non-interactive automation
paths, structured output, progressive help, actionable failures, safe retries,
composable command structure, and bounded responses. It explicitly says to
credit parsing frameworks only for what they supply; structured output,
idempotence, stream discipline, and output bounds remain application work.

This matters because the parser is only one part of the CLI contract. Replacing
one parsing library with another cannot by itself make a CLI agent-ready.

## Current template evidence

The generated project currently has no runtime dependencies
([`template/pyproject.toml.jinja`](../../template/pyproject.toml.jinja)). Its CLI
adapter exposes a useful test seam, `run(argv, ..., out, err) -> int`, and keeps
success data on stdout and diagnostics on stderr. However, it parses with a
manual sequence `match`, has no `--help` or subcommand help, emits prose/tabular
data only, and lists every stored item without a bound
([`cli.py.jinja`](../../template/src/%7B%7B%20package%20%7D%7D/adapters/inbound/cli.py.jinja)).
The integration tests cover the happy path, a domain error, an unknown command,
and real SQLite wiring, but not help discovery, a machine format, output bounds,
detached stdin, or stable error payloads
([`test_cli.py.jinja`](../../template/tests/integration/test_cli.py.jinja)).

The application and repository interfaces currently expose `list_all`, so a
real bounded/paginated query cannot be solved honestly in the parser alone
([`use_cases.py.jinja`](../../template/src/%7B%7B%20package%20%7D%7D/application/use_cases.py.jinja),
[`ports.py.jinja`](../../template/src/%7B%7B%20package%20%7D%7D/application/ports.py.jinja)).

## Primary-source comparison

### `argparse` (stdlib)

Python 3.14's `ArgumentParser` supplies generated help, subparsers, typed
conversion, required arguments, usage errors, and configurable error handling.
Python 3.14 also adds `suggest_on_error` and `color`; `allow_abbrev` and
`exit_on_error` are separately configurable. None of these features supplies a
JSON result contract, idempotence, pagination, or stdout/stderr policy
([Python 3.14 `argparse` documentation](https://docs.python.org/3.14/library/argparse.html)).

For this template, the relevant configuration is:

- `allow_abbrev=False` for predictable flag names;
- `suggest_on_error=True` for corrective feedback;
- `color=False` for byte-stable help without ANSI escapes;
- a `RawDescriptionHelpFormatter` epilog with one example per primary command;
- parser exits/errors translated behind the existing injected-stream seam.

### Click and Typer

Click automatically generates layered help, validates parameters, and provides
`CliRunner`. Its official testing documentation warns that the runner changes
global interpreter state and is not thread-safe. Click also supports prompts,
so non-interactivity still depends on project conventions
([Click help](https://click.palletsprojects.com/en/stable/documentation/),
[Click testing](https://click.palletsprojects.com/en/stable/testing/),
[Click prompts](https://click.palletsprojects.com/en/stable/prompts/)).

Typer builds command and help surfaces from Python type hints and uses a
`CliRunner` test interface. Its documented command handlers are decorated
functions. **Design inference:** that concise form can tempt a template user to
combine CLI translation, composition, and application behavior in one function
([Typer commands](https://typer.tiangolo.com/tutorial/commands/),
[Typer testing](https://typer.tiangolo.com/tutorial/testing/)). Neither Click
nor Typer defines the structured domain output, retry semantics, or query bounds
required by the reviewer.

### Cyclopts and Cappa

Cyclopts derives parameters and help from type hints and docstrings, adds help
by default, and has a `StdioPath` convention for `-` as stdin/stdout
([Cyclopts parameters](https://cyclopts.readthedocs.io/en/stable/parameters.html),
[Cyclopts help](https://cyclopts.readthedocs.io/en/stable/help.html),
[Cyclopts stdin/stdout](https://cyclopts.readthedocs.io/en/stable/cookbook/file_or_stdin_stdout.html)).
Cappa can parse into typed structures or invoke functions and includes its own
dependency-injection mechanism and test runner
([Cappa documentation](https://cappa.readthedocs.io/en/stable/),
[Cappa testing](https://cappa.readthedocs.io/en/stable/testing.html)). These are
attractive for CLI-heavy products. **Design inference:** because the template
already owns composition in `bootstrap.py`, adopting another injection
mechanism would create a competing composition seam.

## Recommendation

Use `argparse` as a **private implementation detail** of the existing inbound
adapter. Do not make the parsing framework the architecture, and do not add a
Copier question offering several frameworks. The current two-command exemplar
does not earn a runtime dependency or a validation matrix of parser variants.

Three deliberately different module designs were compared:

| Design | Depth and locality | Main cost | Decision |
|---|---|---|---|
| Keep manual pattern matching and add typed private commands | Preserves strict typing and the current seam | Reimplements layered help, syntax errors, and examples that `argparse` already owns | Reject as the default; useful only while the CLI has no options or real help |
| Hide `argparse` behind `run` | One small interface; parser, help, errors, and dispatch stay local | Structured output and semantic safety still need explicit design | **Choose for this template** |
| Hide Click (or another framework) behind `run` | Best leverage for a large/lazy command tree | Runtime dependency, ADR, larger conceptual and validation surface | Revisit when a downstream CLI has demonstrated command-tree complexity |

Copying the reviewer prompt into every generated repository is not a substitute
for this design. It would make compliance dependent on a particular agent and
review invocation; executable interface tests provide repeatable evidence, and
the generated `AGENTS.md` can retain the judgment-only extension rules.

The actual integration should be a layered contract:

1. Replace manual matching with a private Python 3.14 `argparse` parser while
   preserving `run(argv, ..., out, err) -> int` as the interface used by callers
   and tests. Do not let `argparse.Namespace` cross into application code.
2. Make data-bearing success output JSON by default, with an explicit human text
   format. Give errors stable codes and write them only to stderr. Keep help
   concise, uncolored, layered, and example-driven.
3. Move list bounding into the application/repository interface (limit plus a
   continuation cursor), rather than materializing or truncating an unbounded
   `list_all()` result in the CLI adapter.
4. Treat mutation retry semantics as a command-specific design decision. The
   sample `add` command should at minimum return the created identifier and make
   its mutation explicit; a generic `--dry-run` flag is not a substitute for
   idempotency. If idempotency is demonstrated, it belongs in the use case and
   persistence contract, not in `argparse`.
5. Extend the existing integration tests into an executable agent-readiness
   contract: top-level and subcommand help, detached stdin/no prompt, exact exit
   codes, JSON parsing and schema keys, clean stdout/stderr, no ANSI, bounded
   default list output, continuation, actionable invalid-input errors, and safe
   retry behavior where promised. Pytest already runs in the quality gate, so a
   framework-specific AST checker would add brittleness without stronger proof.
6. Record the framework/output/pagination decision in a downstream ADR and add a
   compact CLI section to the generated `AGENTS.md`. README examples and the PR
   checklist should point at that contract rather than duplicate it.

This is a deep module shape: callers learn one small `run` interface, while
parsing, help, serialization, and error translation stay local behind it. A
future downstream project can replace the private `argparse` implementation with
Click, Cyclopts, or Cappa without changing the application layer; that is the
right time to adopt a third-party framework, when the CLI's real complexity
provides evidence for it.
