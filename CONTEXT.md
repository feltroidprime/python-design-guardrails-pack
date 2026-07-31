# Python Repository Pack

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
The Root Pack with the One-shot Bootstrap capability removed and only a closed
set of project-identity fields substituted; every other surface remains
identical to the root.
_Avoid_: Template rendering, template directory, repository recursion

**Terminal Project**:
The single user-owned repository emitted by the Root Pack; it may contain
Product Capabilities but cannot create another repository.
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
