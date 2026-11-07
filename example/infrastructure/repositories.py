from uuid import UUID

from alcedo import SqlAlchemyRepository
from sqlalchemy import select

from example.domain.dormitory import Dormitory, DormitoryOccupancy
from example.domain.student import Student


class SqlAlchemyStudentRepository(SqlAlchemyRepository[Student]):
    entity_type = Student

    async def exists_by_number(self, student_no: str) -> bool:
        statement = select(Student.id).where(Student.student_no == student_no)
        return (await self.session.scalar(statement)) is not None


class SqlAlchemyDormitoryRepository(SqlAlchemyRepository[Dormitory]):
    entity_type = Dormitory

    async def find_by_student_id(self, student_id: UUID) -> Dormitory | None:
        statement = (
            select(Dormitory)
            .join(DormitoryOccupancy)
            .where(DormitoryOccupancy.student_id == student_id)
        )
        return await self.session.scalar(statement)
