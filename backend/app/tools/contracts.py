from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, Field


class ToolContext(BaseModel):
    request_id: str = Field(min_length=1)


class ToolResult(BaseModel):
    status: Literal["success", "failed", "unknown"]
    data: dict[str, object] = Field(default_factory=dict)
    error_class: str | None = None
    external_id: str | None = None


class ToolSpec(BaseModel):
    name: str
    handler: Callable[[ToolContext], ToolResult]
