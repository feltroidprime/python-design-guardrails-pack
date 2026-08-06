# pyrepo

The distribution name `pyrepo` and the import package `guardrails_pack` name
one artifact.

This repository is a Terminal Project. A Root Pack projected it once, and it
can create no other repository. The words below name both repositories,
because this one inherits the decision records of `docs/adr/` and the
architecture documents of `pack/docs/architecture/` from the pack that made it.

Read this page before you name a new thing. Use one term for one concept, and
keep that term to the end of the document.

## Language

**Terminal Project**:
This repository. It can contain Product Capabilities, and it cannot create
another repository.
_Avoid_: N0, nested repository, generator

**Root Pack**:
The maintainer-owned project that projected this one. It is the source of a
Pack Update, and it is not this repository.
_Avoid_: Meta-repository, template tree, generated repository

**One-shot Bootstrap**:
The Root Pack's capability to project itself once. Projection deleted it, so
this repository holds no directory, no module and no command of it.
_Avoid_: Recursive generation, self-replication

**Terminal Projection**:
The one operation that produced this repository. It removed the One-shot
Bootstrap capability, substituted the two identity tokens throughout, and
overlaid seven files with a starting version: `README.md`, `CHANGELOG.md`,
`AGENTS.md`, `CONTEXT.md`, `VALIDATION.md`, `.github/workflows/quality.yml`,
and the composition root. Every other file is identical to the Root Pack apart
from the two identity tokens. This repository carries no code of that
operation.
_Avoid_: Template rendering, template directory, repository recursion

**Pack-owned Surface**:
Whole files and directories of replaceable infrastructure projected from the
Root Pack and eligible for controlled pack updates; they contain no product
semantics.
_Avoid_: User code, capability code

**Pack Update**:
An operation performed by the externally installed Root Pack that replaces only
the Pack-owned Surface of this repository.
_Avoid_: Self-update, in-project generator, scaffold migration

**User-owned Surface**:
Whole files and directories containing project identity and Product
Capabilities; pack initialization and updates never overwrite them.
_Avoid_: Scaffold, generated product code

**Product Capability**:
The smallest independently owned vertical product unit inside this repository;
its owned code is its source of truth, without a separate declaration or
lifecycle record.
_Avoid_: Child repository, included repository, registered capability
