# Safe evolution checklist

When you replace a running implementation and the system must stay available,
apply this checklist.

## Strangler Pattern

- Define the stable port before adding the replacement.
- Characterize current behavior with tests.
- Put old and new implementations behind the same contract.
- Define the routing or selection logic outside both implementations.
- Define telemetry that compares outcomes.
- Define rollback before shifting traffic.
- Define the exact deletion condition for the old path.

## Branch by Abstraction

- Introduce the abstraction around the current behavior first.
- Keep that first change behavior-preserving.
- Add the new implementation behind the same abstraction.
- Switch callers incrementally through configuration or through the
  composition root.
- When no caller reaches the old implementation, remove it.
- When one implementation remains, remove the selection code.
- When it has one implementer, remove the temporary abstraction.
- Close the ADR and exception entries.
