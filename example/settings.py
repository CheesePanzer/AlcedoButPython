from pydantic import Field

from alcedo import OptionsBase


class DormitoryOptions(OptionsBase):
    default_capacity: int = Field(default=4, gt=0)
