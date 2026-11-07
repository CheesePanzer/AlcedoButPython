from uuid import UUID

from alcedo import DtoBase


class StudentDto(DtoBase):
    id: UUID
    student_no: str
    name: str
    version: int


class DormitoryDto(DtoBase):
    id: UUID
    code: str
    capacity: int
    student_ids: tuple[UUID, ...]
    version: int
