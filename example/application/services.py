from uuid import UUID

from alcedo import UnitOfWork, transactional

from example.application.commands import (
    DormitoryCreateCommand,
    DormitoryUpdateCommand,
    StudentCreateCommand,
    StudentUpdateCommand,
)
from example.application.dtos import DormitoryDto, StudentDto
from example.domain.dormitory import Dormitory
from example.domain.exceptions import DomainRuleViolation, ResourceNotFound
from example.domain.repositories import DormitoryRepository, StudentRepository
from example.domain.student import Student


class StudentApplicationService:
    def __init__(self, repository: StudentRepository, uow: UnitOfWork) -> None:
        self.repository = repository
        self.uow = uow

    async def get(self, student_id: UUID) -> StudentDto:
        student = await self.repository.get(student_id)
        if student is None:
            raise ResourceNotFound("student", student_id)
        return StudentDto.model_validate(student)

    async def list(self) -> list[StudentDto]:
        students = await self.repository.list()
        return [StudentDto.model_validate(student) for student in students]

    @transactional
    async def create(self, command: StudentCreateCommand) -> UUID:
        if await self.repository.exists_by_number(command.student_no):
            raise DomainRuleViolation("student number already exists")
        student = Student.create(command.student_no, command.name)
        self.repository.add(student)
        return student.id

    @transactional
    async def update(self, student_id: UUID, command: StudentUpdateCommand) -> None:
        student = await self.repository.get(student_id)
        if student is None:
            raise ResourceNotFound("student", student_id)
        student.update(command.name)

    @transactional
    async def delete(self, student_id: UUID) -> None:
        student = await self.repository.get(student_id)
        if student is None:
            return
        await self.repository.remove(student)


class DormitoryApplicationService:
    def __init__(
        self,
        repository: DormitoryRepository,
        students: StudentRepository,
        uow: UnitOfWork,
    ) -> None:
        self.repository = repository
        self.students = students
        self.uow = uow

    @staticmethod
    def _view(dormitory: Dormitory) -> DormitoryDto:
        return DormitoryDto(
            id=dormitory.id,
            code=dormitory.code,
            capacity=dormitory.capacity,
            student_ids=dormitory.student_ids,
            version=dormitory.version,
        )

    async def get(self, dormitory_id: UUID) -> DormitoryDto:
        dormitory = await self.repository.get(dormitory_id)
        if dormitory is None:
            raise ResourceNotFound("dormitory", dormitory_id)
        return self._view(dormitory)

    async def list(self) -> list[DormitoryDto]:
        dormitories = await self.repository.list()
        return [self._view(dormitory) for dormitory in dormitories]

    @transactional
    async def create(self, command: DormitoryCreateCommand) -> UUID:
        dormitory = Dormitory.create(command.code, command.capacity)
        self.repository.add(dormitory)
        return dormitory.id

    @transactional
    async def update(
        self,
        dormitory_id: UUID,
        command: DormitoryUpdateCommand,
    ) -> None:
        dormitory = await self.repository.get_for_update(dormitory_id)
        if dormitory is None:
            raise ResourceNotFound("dormitory", dormitory_id)
        dormitory.update(command.code, command.capacity)

    @transactional
    async def delete(self, dormitory_id: UUID) -> None:
        dormitory = await self.repository.get_for_update(dormitory_id)
        if dormitory is None:
            return
        await self.repository.remove(dormitory)

    @transactional
    async def assign_student(self, dormitory_id: UUID, student_id: UUID) -> None:
        student = await self.students.get(student_id)
        if student is None:
            raise ResourceNotFound("student", student_id)
        assigned = await self.repository.find_by_student_id(student_id)
        if assigned is not None and assigned.id != dormitory_id:
            raise DomainRuleViolation("student is already assigned to another dormitory")
        dormitory = await self.repository.get_for_update(dormitory_id)
        if dormitory is None:
            raise ResourceNotFound("dormitory", dormitory_id)
        dormitory.assign_student(student_id)

    @transactional
    async def remove_student(self, dormitory_id: UUID, student_id: UUID) -> None:
        dormitory = await self.repository.get_for_update(dormitory_id)
        if dormitory is None:
            raise ResourceNotFound("dormitory", dormitory_id)
        dormitory.remove_student(student_id)
