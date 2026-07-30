"""Independent predicates for repository-control verification."""


def canonical_states_match(first_digest: str, second_digest: str) -> bool:
    """Return whether two explicit canonical repository-state digests agree."""
    return first_digest == second_digest
