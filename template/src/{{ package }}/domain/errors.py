"""Domain-specific failures."""


class DomainError(Exception):
    """Base class for stable domain failures."""


class InvalidItemNameError(DomainError):
    """Raised when an item name violates its invariant."""
