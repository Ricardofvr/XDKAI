from __future__ import annotations

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from backend.controller.service import ControllerService


class _ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def _build_request_handler(controller: ControllerService, logger: logging.Logger) -> type[BaseHTTPRequestHandler]:
    class RequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path

            try:
                if path == "/health":
                    self._write_json(HTTPStatus.OK, controller.get_health())
                elif path == "/version":
                    self._write_json(HTTPStatus.OK, controller.get_version_info())
                elif path == "/system/status":
                    self._write_json(HTTPStatus.OK, controller.get_system_status())
                else:
                    self._write_json(
                        HTTPStatus.NOT_FOUND,
                        {"error": "not_found", "message": f"No route for path '{path}'"},
                    )

                logger.info(
                    "api_request_handled",
                    extra={
                        "event": "api_request",
                        "method": "GET",
                        "path": path,
                        "status": getattr(self, "_last_status_code", HTTPStatus.OK),
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "api_request_failed",
                    extra={
                        "event": "api_request_error",
                        "method": "GET",
                        "path": path,
                        "error": str(exc),
                    },
                )
                self._write_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "internal_error", "message": "Unexpected server error."},
                )

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            # Default HTTPServer logging is suppressed in favor of structured logs.
            return

        def _write_json(self, status: HTTPStatus, body: dict[str, Any]) -> None:
            payload = json.dumps(body).encode("utf-8")
            self._last_status_code = status.value
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return RequestHandler


class ApiServer:
    """HTTP API service exposing introspection endpoints only (Week 2)."""

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
