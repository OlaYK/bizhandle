from pydantic import BaseModel, ConfigDict


class PaginationMeta(BaseModel):
    total: int
    limit: int
    offset: int
    count: int
    has_next: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 42,
                "limit": 10,
                "offset": 0,
                "count": 10,
                "has_next": True,
            }
        }
    )


class ValidationIssueOut(BaseModel):
    field: str
    message: str
    type: str | None = None


class ErrorDetailOut(BaseModel):
    code: str
    message: str
    request_id: str
    path: str
    details: list[ValidationIssueOut] | None = None


class ErrorOut(BaseModel):
    error: ErrorDetailOut

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "code": "bad_request",
                    "message": "Invalid request payload",
                    "request_id": "8d8f2b00-6c79-4a45-8ff4-b0a5f2bc4bc2",
                    "path": "/sales",
                    "details": None,
                }
            }
        }
    )
