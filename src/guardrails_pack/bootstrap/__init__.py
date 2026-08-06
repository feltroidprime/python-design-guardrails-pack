"""The One-shot Bootstrap: the capability that projects this pack once.

This directory is the one Product Capability of the Root Pack. Terminal
Projection deletes it, so a Terminal Project holds no directory, no module and
no command of it, and it can never create another repository.

The capability is checked like every other capability. It holds `api.py`,
`domain/`, `application/`, `adapters/inbound/`, `adapters/outbound/`,
`proof.toml` and `tests/`. It also holds `initial/`, the seven files a new
project starts with. One of them is the quality workflow, which holds no job
for the suite this directory carries. Three more are `AGENTS.md`, `CONTEXT.md`
and `VALIDATION.md`, because a project cannot act on the pack's version of any
of them. ADR-0009 states the rule.
"""
