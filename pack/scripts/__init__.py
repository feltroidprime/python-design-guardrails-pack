"""Index of the local quality tooling under `pack/scripts/`.

`pack/configs/prek.toml` runs twelve local hooks, in this order: `lockfile`,
`format`, `lint`, `types`, `dependencies`, `architecture`, `docs`, `proof`,
`symbolic`, `import-contracts`, `tests`, `manifest`. The first five hooks run
a third-party tool directly and own no module here. The other seven map to
the modules below.

| Hook | Module | Codes it can report |
|---|---|---|
| `architecture` | `architecture_guard.py` | `ARCH000` |
| | `architecture_rules.py` | `ARCH001`-`ARCH015` |
| | `none_discipline.py` | `ARCH016`-`ARCH018` |
| | `path_discipline.py` | `ARCH019`, `ARCH020`, `ARCH028` |
| | `cli_discipline.py` | `ARCH021`-`ARCH023` |
| | `cli_surface.py` | `CLI001`-`CLI004` |
| | `review_discipline.py` | `ARCH026`, `ARCH027`, `ARCH029` |
| | `override_discipline.py` | `ARCH030` |
| `docs` | `docs_guard.py` | `DOC001`-`DOC007` |
| `proof` | `proof_guard.py` | `PROOF000` |
| | `proof_target_rules.py` | `PROOF001`-`PROOF009`, `PROOF027` |
| | `proof_evidence_rules.py` | `PROOF010`-`PROOF021`, `PROOF026`, `PROOF028` |
| | `proof_oracle_rules.py` | `PROOF022`-`PROOF025` |
| `symbolic` | `crosshair_gate.py` | none (it reports the exit status of CrossHair) |
| `import-contracts` | `import_contracts.py` | none (it reports the exit status of `lint-imports`) |
| `manifest` | `manifest_guard.py` | none (it reports a manifest disagreement, not a code) |

`architecture_guard.py` states the marker range that governs every `ARCH`
code, in a table. `architecture_rules.py` names every `ARCH001`-`ARCH015`
code and its fix, in a table of its own. `none_discipline.py`,
`path_discipline.py`, `cli_discipline.py`, `review_discipline.py`, and
`override_discipline.py` name their own codes the same way, each in its
first line. `cli_surface.py` names `CLI001`-`CLI004` in a table. `proof_guard.py`
maps every `PROOF` code to the module that owns it.

`identity.py` and `ownership.py` carry facts that most modules above depend
on: the import package name, the capability list, and the pack-owned
predicate. `architecture_policy.py` loads the limits and conventions of
`pack/architecture.toml`. `doctor.py` and `release.py` back the `just doctor`
and `just release` recipes. Neither one runs inside the gate.
`agent_sessions.py` is a private loader that the opt-in session-evidence
tests use.
"""
