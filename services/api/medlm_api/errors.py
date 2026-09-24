class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, retryable: bool = False):
        self.status = status
        self.code = code
        self.message = message
        self.retryable = retryable


def unavailable(component: str) -> AppError:
    return AppError(503, "not_configured", f"{component} is not configured.")
