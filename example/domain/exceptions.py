from uuid import UUID

from alcedo import ConflictError, NotFoundError


class DomainError(ConflictError):
    pass


class ResourceNotFound(NotFoundError):
    def __init__(self, resource: str, resource_id: UUID) -> None:
        super().__init__(f"{resource} {resource_id} was not found")


class DomainRuleViolation(DomainError):
    pass
