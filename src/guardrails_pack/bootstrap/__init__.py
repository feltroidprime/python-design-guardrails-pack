"""The One-shot Bootstrap: the capability that projects this pack once.

This directory is the one Product Capability of the Root Pack. Terminal
Projection deletes it, so a Terminal Project holds no directory, no module and
no command of it, and it can never create another repository.

The capability is checked like every other capability. It holds `api.py`,
`domain/`, `application/`, `adapters/inbound/`, `adapters/outbound/`,
`proof.toml` and `tests/` (rule L1 of #85 section 4.3). It also holds
`initial/`, the four files a new project starts with. The fourth is the
quality workflow, which holds no job for the suite this directory carries.
"""
