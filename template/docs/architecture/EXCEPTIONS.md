# Architecture exception ledger

## ADR-0003 — agent observability operator adapters

- Diagnostics: Ruff `S603` and `S606` in
  `scripts/agent_observability_codex_hook.py`, Ruff `S603` in
  `scripts/agent_observability_support.py`, and Ruff `S310` in
  `scripts/agent_observability_transcripts.py`.
- Owner: repository maintainers.
- Reason: the operator must execute reviewed Codex, Claude Code, Node, and Git
  binaries with shell-free argv, replace the hook process with the pinned Node
  entrypoint, and call a contributor-selected Langfuse deployment through the
  standard-library HTTP client.
- Risk: a compromised executable on `PATH` could run during explicit setup; a
  contributor could direct sensitive transcripts to the wrong HTTP(S) host.
- Controls: explicit opt-in, pinned Git commits, executable/version checks,
  clean working-tree checks before reuse/execution, installed-Claude-tree byte
  comparison, absolute HTTP(S)-only base URLs, exclusive mode-`0600` temporary
  credential files, and no subprocess shell.
- Revisit trigger: either integration gains a project-scoped SDK/API that
  removes the subprocess or `urlopen` boundary.
- Removal criteria: delete each exclusion with the corresponding external
  boundary.

Each exception must include:

- ADR identifier;
- exact files/imports/diagnostics covered;
- owner;
- reason the normal rule cannot currently hold;
- risk introduced;
- expiry date or objective revisit trigger;
- removal criteria.

Suppressions in code must use a narrow code and include `ARCH-EXCEPTION: ADR-XXXX`.
