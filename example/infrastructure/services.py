from alcedo import AlcedoRuntime, UnitOfWork

from example.application.services import (
    DormitoryApplicationService,
    StudentApplicationService,
)
from example.domain.repositories import DormitoryRepository, StudentRepository
from example.infrastructure.repositories import (
    SqlAlchemyDormitoryRepository,
    SqlAlchemyStudentRepository,
)


def add_example_services(runtime: AlcedoRuntime) -> None:
    services = runtime.services
    services.add_scoped(StudentRepository, SqlAlchemyStudentRepository)
    services.add_scoped(DormitoryRepository, SqlAlchemyDormitoryRepository)
    services.add_scoped(StudentApplicationService)
    services.add_scoped(DormitoryApplicationService)
