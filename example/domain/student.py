from alcedo import AggregateRoot
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from example.domain.exceptions import DomainRuleViolation


class Student(AggregateRoot):
    __tablename__ = "students"

    student_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    @classmethod
    def create(cls, student_no: str, name: str) -> "Student":
        student_no = student_no.strip()
        name = name.strip()
        if not student_no:
            raise DomainRuleViolation("student number cannot be empty")
        if not name:
            raise DomainRuleViolation("student name cannot be empty")
        return cls(student_no=student_no, name=name)

    def update(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise DomainRuleViolation("student name cannot be empty")
        self.name = name
