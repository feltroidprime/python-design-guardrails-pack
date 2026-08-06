# Python Design Guardrails Pack

The repository name `python-design-guardrails-pack`, the distribution name
`pyrepo`, and the import package `guardrails_pack` name one artifact.

This context describes one self-hosting root project and the single user-owned
project obtained by projecting that root.

## Language

**Root Pack**:
The maintainer-owned project and sole source of truth; it has the same contract
as a Terminal Project plus the One-shot Bootstrap capability.
_Avoid_: Meta-repository, template tree, generated repository

**One-shot Bootstrap**:
The Root Pack's capability to project itself into one Terminal Project without
copying that capability into the result.
_Avoid_: Recursive generation, self-replication

**Terminal Projection**:
The Root Pack with the One-shot Bootstrap capability removed, its two identity
tokens substituted throughout, and four files overlaid with a starting
version. `README.md`, `CHANGELOG.md`, `.github/workflows/quality.yml`, and the
composition root are the four overlaid files. Every other file is identical to
the root apart from the two identity tokens.
_Avoid_: Template rendering, template directory, repository recursion

**Terminal Project**:
The single user-owned repository emitted by the Root Pack. It can contain
Product Capabilities, and it cannot create another repository.
_Avoid_: N0, nested repository, generator

**Pack-owned Surface**:
Whole files and directories of replaceable infrastructure projected from the
Root Pack and eligible for controlled pack updates; they contain no product
semantics.
_Avoid_: User code, capability code

**Pack Update**:
An operation performed by the externally installed Root Pack that replaces only
the Pack-owned Surface of a Terminal Project.
_Avoid_: Self-update, in-project generator, scaffold migration

**User-owned Surface**:
Whole files and directories containing project identity and Product
Capabilities; pack initialization and updates never overwrite them.
_Avoid_: Scaffold, generated product code

**Product Capability**:
The smallest independently owned vertical product unit inside a Terminal
Project; its owned code is its source of truth, without a separate declaration
or lifecycle record.
_Avoid_: Child repository, included repository, registered capability
