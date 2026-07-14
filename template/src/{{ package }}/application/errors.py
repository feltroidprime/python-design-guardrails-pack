"""Application-level failures raised at port boundaries."""


class RepositoryError(Exception):
    """Raised when a repository implementation cannot honor its contract."""
