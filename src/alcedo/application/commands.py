from pydantic import BaseModel, ConfigDict


class CommandBase(BaseModel):
    """Base for validated application use-case input."""

    model_config = ConfigDict(extra="forbid")
