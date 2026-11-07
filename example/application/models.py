from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StudentCreate(BaseModel):
    student_no: str = Field(max_length=32)
    name: str = Field(max_length=100)


class StudentUpdate(BaseModel):
    name: str = Field(max_length=100)


class StudentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_no: str
    name: str
    version: int


class DormitoryCreate(BaseModel):
    code: str = Field(max_length=32)
    capacity: int = Field(gt=0)


class DormitoryUpdate(BaseModel):
    code: str = Field(max_length=32)
    capacity: int = Field(gt=0)


class DormitoryView(BaseModel):
    id: UUID
    code: str
    capacity: int
    student_ids: tuple[UUID, ...]
    version: int


class AssignStudent(BaseModel):
    student_id: UUID
