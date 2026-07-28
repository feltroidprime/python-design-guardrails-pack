# Validation record — 2026-07-28

Validated on macOS 26 Apple Silicon with Python 3.14.6, uv 0.11.28, just
1.56.0, Copier 9.17.0, pytest 9.1.1, and pytest-xdist 3.8.0. Copier emitted the
usual `DirtyLocalWarning` instances because the canonical template changes were
intentionally uncommitted.

## Change validated

The previous record stated that the `symbolic core` gate step passed vacuously:
CrossHair aborted with `CrosshairUnsupported: error constructing ItemId
instance` and still exited zero. This change makes the symbolic layer real and,
more importantly, makes an empty symbolic run fail instead of pass.

1. **Copy protocol on invariant-guarded dataclasses.** CrossHair's
   `manual_constructor` builds an instance with `typ.__new__(typ)` and then
   calls `__init__`; because `@icontract.invariant` wraps `__init__`, CrossHair's
   enforcement wrapper snapshots each argument with `copy.copy`. For a
   `slots=True` dataclass that reaches `dataclasses._dataclass_getstate`, which
   eagerly reads every field of a not-yet-initialised instance and raises
   `AttributeError`. `ItemId`, `ItemName`, `Item`, and `ItemCreatedEvent` now
   define a defensive `__getstate__` alongside the `__setstate__` they already
   carried. For a fully constructed value it is byte-identical to the dataclass
   default. No guardrail moved: `frozen=True, slots=True, kw_only=True`
   (ARCH007) and the invariants are unchanged.
2. **The symbolic layer carries its own canary.**
   `verification/harness/symbolic_canary.py` states a deliberately false
   postcondition over the union of the argument types the real symbolic targets
   accept. `scripts/crosshair_gate.py` fails unless CrossHair refutes it.
   Removing the `__getstate__` fix turns the canary from `refuted (expected)`
   into `NOT refuted: the symbolic layer cannot reason about the domain types`
   and fails the gate, which is exactly the state the previous record described
   as a silent pass.
3. **Per-target symbolic reporting.** The gate now analyses one target per
   process with `--report_all` and prints `owner | target | status`. Failures are
   reported under `PROPERTY[<ID>]`, so a CrossHair counterexample is traceable to
   its catalog entry the same way an `icontract` or Hypothesis failure is.
4. **One falsifying canary per oracle (PROOF021 rewritten, PROOF028 added).** A
   single canary over a conjunction of two oracles stays false when either
   operand degenerates to `return True`, so it pins neither. Measured: with the
   previous single canary, mutating `item_name_text_is_canonical` to `return
   True` passed the proof guard, all 16 proof tests, CrossHair, and all 149
   example tests. The guard now requires one canary per declared oracle whose
   assertion depends on that oracle alone, and rejects the conjoined shape.
5. **Oracle purity follows same-module private helpers.** `discover_oracle` now
   unions the called names and forbidden statements of every module-level
   function the oracle can reach, so an effectful builtin (`open`, `print`,
   `eval`, …) hidden one call deep no longer escapes PROOF023.
6. **Valid-input generators reach the specification's boundaries.**
   `item_ids()` previously drew only from characters that survive `strip()`, so
   a valid padded or space-containing identifier was never generated even though
   `ItemId` deliberately does not normalize. `item_names()` capped generated text
   at 40 characters, so `MAX_ITEM_NAME_LENGTH` was unreachable from the valid
   side and no valid name ever contained an inner space. Both now generate
   single-line text filtered on visibility, plus explicit boundary samples.
7. **Honest scope for `CREATE-ITEM-REPLAY-SAFE`.** The state machine only ever
   submits non-empty idempotency keys, so the unkeyed `CreateItem.__call__`
   branch was never exercised by the property that targets that method. The
   assumption is now stated in `proof.toml` instead of being implied.

## Commands and actual results

```bash
just validate
```

- `just test`: **317 passed**, 26 expected warnings, 66.8 s.
- `scripts/validate_pack.py`: **passed** — template clean, instantiation fully
  rendered, bootstrap repaired drift, generated pre-commit and pre-push shims
  and the full generated quality gate all green from a linked worktree.
- `PACK_RUN_DOWNSTREAM_GATE=1 pytest tests/test_update_roundtrip.py`: **1 passed,
  1 failed**. `test_previous_release_updates_cleanly_to_current_ref` fails its
  optional downstream-gate assertion on `ruff format` drift in the merged tree.
  This failure reproduces unchanged on a clean clone of commit `5668b33`, so it
  predates this change and is not caused by it. Without the environment variable
  (the plain `just test` lane) the same test passes.

### Generated repository, instantiated fresh and synced

```bash
uv run python -m scripts.proof_guard   # Proof contract passed: 8 properties, 3 CrossHair target(s).
just prove                             # 17 proof tests passed; 4 symbolic targets; exit 0; ~9 s
just prove-deep                        # 17 proof tests passed (50 s); 4 symbolic targets; exit 0; 108 s
uv run python scripts/quality_gate.py  # All quality gates passed; branch coverage 94%
```

`just prove` symbolic output:

```
CrossHair (fast): 4 target(s)
  CREATE-ITEM-PRESERVES-FACTS | acme_orders.domain.decisions:create_item | searched, no counterexample (bounded)
  ITEM-CREATED-EVENT-MIRRORS-ITEM | acme_orders.domain.decisions:item_created_event | searched, no counterexample (bounded)
  RENAME-ITEM-PRESERVES-IDENTITY | acme_orders.domain.decisions:rename_item | searched, no counterexample (bounded)
  SYMBOLIC-CANARY | verification.harness.symbolic_canary:refutable_echo | refuted (expected)
```

### Fault sensitivity of the symbolic layer

With `rename_item` changed to return `item.name` instead of `new_name`,
`uv run python -m scripts.crosshair_gate ci` exits **1** and reports:

```
  RENAME-ITEM-PRESERVES-IDENTITY | acme_orders.domain.decisions:rename_item | counterexample found

PROPERTY[RENAME-ITEM-PRESERVES-IDENTITY] acme_orders.domain.decisions:rename_item
src/acme_orders/domain/decisions.py:59: error: "def _rename_item_holds(...) -> bool:" yields false when calling rename_item(Item(item_id=ItemId(value='\x00'), name=ItemName(value='\x07')), ItemName(value='\x05'))
```

Before this change the same fault exited 0 in 0.32 s.

## Tests added or updated

- `tests/test_crosshair_gate.py`: the gate analyses each target and the canary
  separately with the recorded budget flags; an unrefuted canary fails the gate;
  a counterexample is reported under its owning property ID.
- `tests/test_proof_guard.py`: a canary conjoining two oracles raises
  PROOF028/PROOF021; one canary per oracle closes the chain; an effectful
  builtin behind a private specification helper raises PROOF023; an unexpired
  `[[exemptions]]` entry closes the surface and an expired one reopens it
  (the expiry rule existed but had no test).
- `tests/test_instantiate.py`: `verification/harness/symbolic_canary.py` added
  to the expected file list; `EXPECTED_GENERATED_TREE_SHA256` updated to
  `411324c7515ad2205b0e4ffcf5a31a2ee13e3671159e2d146aacb8db91eb239d`.
- `template/tests/unit/domain/test_value_objects.py.jinja`: every
  invariant-guarded value survives a `copy.copy`/`copy.deepcopy` round trip,
  which is the protocol the symbolic layer depends on.
- `template/verification/tests/test_value_object_properties.py.jinja`:
  `ITEM-NAME-CANONICAL` now owns one canary per oracle.

## Remaining risks and portability notes

- **Bounded search is not proof.** CrossHair reports `searched, no counterexample
  (bounded)` for all three real targets at every profile, including `deep`. The
  domain's input space is unbounded strings, so `Confirmed over all paths` is
  unreachable here and cannot be required. The canary establishes that the
  search machinery is live; it does not establish coverage of the target's
  input space.
- **Source mutation is invisible to CrossHair.** The `rename_item` postcondition
  reads the source item after the body has run, so mutating the source in place
  satisfies it. That mutation is caught by the Hypothesis proof (which snapshots
  the source and asserts `result is not item`), not by the symbolic layer.
- The `z3-solver!=5.0.0.0` constraint is still a workaround for one upstream
  release; drop it once a correctly tagged release exists.
- The update round-trip's optional downstream gate is red on this branch (see
  above) and needs a separate fix.
