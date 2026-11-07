from typing import Any

from pydantic import BaseModel, ConfigDict


class ProblemDetails(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    title: str
    status: int
    detail: str
    instance: str
    traceId: str

    def response_content(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)
