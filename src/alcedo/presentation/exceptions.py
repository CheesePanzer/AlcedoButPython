class AlcedoError(Exception):
    """Base for errors that are safe to expose to API clients."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        client_action: str | None = None,
    ) -> None:
        super().__init__(message)
        self.friendly_message = message
        self.code = code or type(self).__name__
        self.client_action = client_action


class NotFoundError(AlcedoError):
    pass


class UnauthorizedError(AlcedoError):
    pass


class ForbiddenError(AlcedoError):
    pass


class BadRequestError(AlcedoError):
    pass


class ConflictError(AlcedoError):
    pass


class TooManyRequestsError(AlcedoError):
    pass
