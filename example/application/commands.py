from uuid import UUID

from alcedo import CommandBase
from pydantic import Field


class StudentCreateCommand(CommandBase):
    student_no: str = Field(max_length=32)
    name: str = Field(max_length=100)


class StudentUpdateCommand(CommandBase):
    name: str = Field(max_length=100)


class DormitoryCreateCommand(CommandBase):
    code: str = Field(max_length=32)
    capacity: int = Field(gt=0)


class DormitoryUpdateCommand(CommandBase):
    code: str = Field(max_length=32)
    capacity: int = Field(gt=0)


class AssignStudentCommand(CommandBase):
    student_id: UUID
