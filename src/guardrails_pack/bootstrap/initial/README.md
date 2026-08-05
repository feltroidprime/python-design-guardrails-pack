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

`just check` runs the one gate of this repository: twelve `prek` hooks, the same
twelve that CI runs. `just prove` is the fast local proof loop. `pyrepo` is the
command line of this project, and it lists the capabilities you compose.

## Add a capability

A capability is one directory directly under `src/guardrails_pack/`, and one
import line in `src/guardrails_pack/composition.py`.

```
src/guardrails_pack/orders/
├── api.py                 the public functions, which become subcommands
├── domain/                pure rules, with no I/O
├── application/           the ordered steps
├── adapters/inbound/      the ways in
├── adapters/outbound/     the ways out
├── proof.toml             the laws this capability owns
└── tests/
```

Import the `api` module in `composition.py` and add it to `CAPABILITIES`. The
command line then carries `pyrepo orders <function>` for every public function
of `api.py`. Nothing else records the capability, and a directory that
`composition.py` never imports is simply not composed yet.

## Two ownership zones

`pack/` and every `_`-prefixed name under `src/guardrails_pack/` are pack-owned.
An update of the pack replaces those whole files, and it never writes anything
else. Everything else is yours, including `pyproject.toml`, `composition.py`,
`cli.py` and `tests/`.

Four files at the root are thin entry points into `pack/`: `justfile`,
`pyrightconfig.json`, `.python-version` and `.github/workflows/quality.yml`. An
update reports a suggested change to them and never applies one.

## Documents

- `AGENTS.md` — the contract for every coding agent in this repository.
- `docs/README.md` — the documentation map.
- `pack/docs/architecture/` — the rules the gate carries.
