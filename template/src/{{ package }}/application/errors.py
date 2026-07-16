"""Application-level failures raised at port boundaries."""


class RepositoryError(Exception):
    """Raised when a repository implementation cannot honor its contract."""


class IdempotencyConflictError(Exception):
    """Raised when one key is reused for a different normalized request."""


class InvalidIdempotencyKeyError(Exception):
    """Raised when a caller supplies an unusable conditional-idempotency key."""
