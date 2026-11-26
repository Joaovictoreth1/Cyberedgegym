from collections.abc import Mapping

from starlette.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers


def error_response(error: ApiError, fields: list[dict[str, str]] | None = None) -> JSONResponse:
    payload: dict[str, object] = {"code": error.code, "message": error.message}
    if fields:
        payload["fields"] = fields
    return JSONResponse({"error": payload}, status_code=error.status, headers=error.headers)
