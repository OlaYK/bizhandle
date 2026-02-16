from app.schemas.common import ErrorOut


_ERROR_EXAMPLES: dict[int, tuple[str, str]] = {
    400: ("bad_request", "Bad request"),
    401: ("unauthorized", "Unauthorized"),
    403: ("forbidden", "Forbidden"),
    404: ("not_found", "Resource not found"),
    409: ("conflict", "Conflict"),
    422: ("validation_error", "Validation error"),
    429: ("rate_limited", "Too many requests"),
    500: ("internal_error", "Internal server error"),
}


def error_responses(*status_codes: int) -> dict[int, dict]:
    responses: dict[int, dict] = {}
    for status_code in status_codes:
        code, message = _ERROR_EXAMPLES.get(status_code, ("http_error", "HTTP error"))
        responses[status_code] = {
            "model": ErrorOut,
            "description": message,
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": code,
                            "message": message,
                            "request_id": "request-id",
                            "path": "/example",
                            "details": None,
                        }
                    }
                }
            },
        }
    return responses
