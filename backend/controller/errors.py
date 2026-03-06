from __future__ import annotations


class ControllerRequestError(RuntimeError):
    """Controller-level request error for API-safe propagation."""

    def __init__(self, message: str, *, error_type: str, status_code: int) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code
