from uuid import UUID

from alcedo import AggregateRoot, Entity
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from example.domain.exceptions import DomainRuleViolation


class Dormitory(AggregateRoot):
    __tablename__ = "dormitories"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    _occupancies: Mapped[list["DormitoryOccupancy"]] = relationship(
        back_populates="_dormitory",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def student_ids(self) -> tuple[UUID, ...]:
        return tuple(item.student_id for item in self._occupancies)

    @classmethod
    def create(cls, code: str, capacity: int) -> "Dormitory":
        code = code.strip()
        if not code:
            raise DomainRuleViolation("dormitory code cannot be empty")
        if capacity <= 0:
            raise DomainRuleViolation("capacity must be greater than zero")
        return cls(code=code, capacity=capacity)

    def update(self, code: str, capacity: int) -> None:
        code = code.strip()
        if not code:
            raise DomainRuleViolation("dormitory code cannot be empty")
        if capacity < len(self._occupancies):
            raise DomainRuleViolation("capacity cannot be lower than current occupancy")
        self.code = code
        self.capacity = capacity

    def assign_student(self, student_id: UUID) -> None:
        if student_id in self.student_ids:
            return
        if len(self._occupancies) >= self.capacity:
            raise DomainRuleViolation("dormitory is full")
        self._occupancies.append(DormitoryOccupancy(student_id=student_id))

    def remove_student(self, student_id: UUID) -> None:
        occupancy = next(
            (item for item in self._occupancies if item.student_id == student_id),
            None,
        )
        if occupancy is not None:
            self._occupancies.remove(occupancy)


class DormitoryOccupancy(Entity):
    __tablename__ = "dormitory_occupancies"
    __table_args__ = (UniqueConstraint("student_id"),)

    dormitory_id: Mapped[UUID] = mapped_column(
        ForeignKey("dormitories.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), nullable=False
    )
    _dormitory: Mapped[Dormitory] = relationship(back_populates="_occupancies")
