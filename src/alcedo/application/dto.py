from pydantic import BaseModel, ConfigDict


class DtoBase(BaseModel):
    """Base for data returned across the application boundary."""

    model_config = ConfigDict(from_attributes=True)
