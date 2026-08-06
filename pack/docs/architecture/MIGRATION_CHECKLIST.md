# Safe evolution checklist

## Strangler Pattern

- Define the stable port before adding the replacement.
- Characterize current behavior with tests.
- Put old and new implementations behind the same contract.
- Define routing/selection outside both implementations.
- Define telemetry that compares outcomes.
- Define rollback before shifting traffic.
- Define the exact deletion condition for the old path.

## Branch by Abstraction

- Introduce the abstraction around the current behavior first.
- Keep that first change behavior-preserving.
- Add the new implementation behind the same abstraction.
- Switch callers incrementally through configuration/composition root.
- Remove the old implementation, switch, and temporary abstraction when no longer needed.
- Close the ADR and exception entries.
