from __future__ import annotations

import json
import logging
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from backend.controller import ControllerRequestError, ControllerService

from .errors import ApiError, ApiValidationError
from .openai_schema import parse_chat_completions_request, parse_embeddings_request


class _ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def _build_request_handler(controller: ControllerService, logger: logging.Logger) -> type[BaseHTTPRequestHandler]:
    class RequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self._dispatch(method="GET")

        def do_POST(self) -> None:  # noqa: N802
            self._dispatch(method="POST")

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            # Default HTTPServer logging is suppressed in favor of structured logs.
            return

        def _dispatch(self, method: str) -> None:
            path = urlparse(self.path).path
            request_id = self.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:20]}"

            logger.info(
                "api_request_received",
                extra={
                    "event": "api_request",
                    "phase": "received",
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "client": self.client_address[0] if self.client_address else None,
                },
            )

            try:
                response_status, response_body = self._route_request(method=method, path=path, request_id=request_id)
                self._write_json(response_status, response_body, request_id=request_id)

                logger.info(
                    "api_request_handled",
                    extra={
                        "event": "api_request",
                        "phase": "handled",
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status": response_status.value,
                    },
                )
            except ApiError as exc:
                self._write_json(HTTPStatus(exc.status_code), exc.to_payload(), request_id=request_id)
                logger.warning(
                    "api_request_error",
                    extra={
                        "event": "api_request_error",
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status": exc.status_code,
                        "error_type": exc.error_type,
                        "error_message": exc.message,
                    },
                )
            except ControllerRequestError as exc:
                api_error = ApiError(
                    status_code=exc.status_code,
                    error_type=exc.error_type,
                    message=str(exc),
                    request_id=request_id,
                )
                self._write_json(HTTPStatus(api_error.status_code), api_error.to_payload(), request_id=request_id)
                logger.warning(
                    "controller_request_error",
                    extra={
                        "event": "api_request_error",
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status": api_error.status_code,
                        "error_type": api_error.error_type,
                        "error_message": api_error.message,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "api_request_unhandled_exception",
                    extra={
                        "event": "api_request_error",
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "error": str(exc),
                    },
                )
                api_error = ApiError(
                    status_code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
                    error_type="internal_error",
                    message="Unexpected server error.",
                    request_id=request_id,
                )
                self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, api_error.to_payload(), request_id=request_id)

        def _route_request(self, method: str, path: str, request_id: str) -> tuple[HTTPStatus, dict[str, Any]]:
            if method == "GET" and path == "/health":
                return HTTPStatus.OK, controller.get_health()
            if method == "GET" and path == "/version":
                return HTTPStatus.OK, controller.get_version_info()
            if method == "GET" and path == "/system/status":
                return HTTPStatus.OK, controller.get_system_status()

            if method == "GET" and path == "/v1/models":
                return HTTPStatus.OK, controller.list_models()

            if method == "POST" and path == "/v1/chat/completions":
                payload = self._read_json_body(request_id=request_id)
                chat_request = parse_chat_completions_request(payload, request_id=request_id)
                response = controller.create_chat_completion(chat_request)
                return HTTPStatus.OK, response

            if method == "POST" and path == "/v1/embeddings":
                payload = self._read_json_body(request_id=request_id)
                embeddings_request = parse_embeddings_request(payload, request_id=request_id)
                response = controller.create_embeddings(embeddings_request)
                return HTTPStatus.OK, response

            raise ApiError(
                status_code=HTTPStatus.NOT_FOUND.value,
                error_type="not_found",
                message=f"No route for path '{path}'",
                request_id=request_id,
            )

        def _read_json_body(self, request_id: str) -> Any:
            content_length_raw = self.headers.get("content-length")
            if content_length_raw is None:
                raise ApiValidationError("Missing required 'Content-Length' header.", request_id=request_id)

            try:
                content_length = int(content_length_raw)
            except ValueError as exc:
                raise ApiValidationError("Invalid 'Content-Length' header.", request_id=request_id) from exc

            if content_length <= 0:
                raise ApiValidationError("Request body must not be empty.", request_id=request_id)

            raw_body = self.rfile.read(content_length)
            try:
                return json.loads(raw_body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ApiValidationError("Request body must be valid JSON.", request_id=request_id) from exc

        def _write_json(self, status: HTTPStatus, body: dict[str, Any], request_id: str | None = None) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            if request_id:
                self.send_header("x-request-id", request_id)
            self.end_headers()
            self.wfile.write(payload)

    return RequestHandler


class ApiServer:
    """HTTP API service exposing introspection and OpenAI-style endpoints."""

    def __init__(self, host: str, port: int, controller: ControllerService, logger: logging.Logger) -> None:
        self._host = host
        self._port = port
        self._logger = logger
        handler = _build_request_handler(controller, logger)
        self._server = _ReusableThreadingHTTPServer((host, port), handler)

    def start(self) -> None:
        self._logger.info(
            "api_server_starting",
            extra={"event": "startup_step", "step": "api_server_starting", "host": self._host, "port": self._port},
        )
        self._server.serve_forever()

    def shutdown(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._logger.info("api_server_stopped", extra={"event": "shutdown_step", "step": "api_server_stopped"})
