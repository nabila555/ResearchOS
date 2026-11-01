"""Service-layer errors. The API maps them to HTTP responses in app.main."""


class ServiceError(Exception):
    status_code = 400

    def __init__(self, message: str, **extra: object) -> None:
        super().__init__(message)
        self.message = message
        self.extra = extra


class NotFoundError(ServiceError):
    status_code = 404


class ConflictError(ServiceError):
    status_code = 409


class InvalidRequestError(ServiceError):
    status_code = 400
