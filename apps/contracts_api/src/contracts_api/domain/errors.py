class DomainError(Exception):
    """Base domain error."""


class ValidationError(DomainError):
    """Invalid domain input."""


class NotFoundError(DomainError):
    """Aggregate not found or not visible to actor."""


class ForbiddenError(DomainError):
    """Actor cannot access the resource."""


class ConflictError(DomainError):
    """Optimistic concurrency conflict."""
