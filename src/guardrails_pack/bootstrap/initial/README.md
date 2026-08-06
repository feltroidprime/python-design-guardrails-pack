# pyrepo

A Python 3.14 application with an executable architecture and quality contract.

This repository starts with no product capability. The structure, the tool
policy and the gate are here from the first commit, and the product model stays
your decision.

## Commands

```bash
just check
just prove
uv run pyrepo --help
```

`just check` runs the one gate of this repository: eleven upstream file hooks,
then twelve local hooks. CI runs the same command, so a local run and CI cannot
disagree. `just prove` is the fast local proof loop. `pyrepo` is the command
line of this project, and it lists the capabilities you compose.

## Add a capability

A capability is one directory directly under `src/guardrails_pack/`, and one
import line in `src/guardrails_pack/composition.py`.

```
src/guardrails_pack/orders/
├── api.py                 the public functions, which become subcommands
├── adapters/inbound/      the ways in
├── adapters/outbound/     the ways out
├── application/           the ordered steps
├── domain/                pure rules, with no I/O
├── proof.toml             the laws this capability owns
└── tests/
```

Import the `api` module in `composition.py` and add it to `CAPABILITIES`. The
command line then carries `pyrepo orders <function>` for every public function
of `api.py`. Nothing else records the capability, and a directory that
`composition.py` never imports is simply not composed yet.

`AGENTS.md` states the four layout rules and the four command-line rules the
gate enforces. Read it before you write the first module.

## Two ownership zones

`pack/`, every `_`-prefixed name under `src/guardrails_pack/`, and `py.typed`
are pack-owned. An update of the pack replaces those whole files, and it never
writes anything else. Everything else is yours: `pyproject.toml`,
`composition.py`, `cli.py`, and every test you write.

Four files at the root are thin entry points into `pack/`: `justfile`,
`pyrightconfig.json`, `.python-version` and `.github/workflows/quality.yml`. An
update reports a suggested change to them and never applies one.

## Documents

- `AGENTS.md` — the contract for every coding agent in this repository.
- `CONTEXT.md` — the vocabulary, and the words each concept retired.
- `docs/README.md` — the documentation map.
- `pack/docs/architecture/` — the rules the gate carries.
