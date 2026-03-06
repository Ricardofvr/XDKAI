from __future__ import annotations

from http import HTTPStatus
from typing import Any


class ApiError(RuntimeError):
    """Represents a structured API error response."""

    def __init__(self, *, status_code: int, error_type: str, message: str, request_id: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.message = message
        self.request_id = request_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "error": {
                "type": self.error_type,
                "message": self.message,
                "request_id": self.request_id,
            }
        }


class ApiValidationError(ApiError):
    def __init__(self, message: str, request_id: str | None = None) -> None:
        super().__init__(
            status_code=HTTPStatus.BAD_REQUEST.value,
            error_type="invalid_request_error",
            message=message,
            request_id=request_id,
        )
