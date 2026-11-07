from uuid import UUID

from fastapi import APIRouter, Response, status

from alcedo import Created, Inject, NoContent
from example.application.models import (
    AssignStudent,
    DormitoryCreate,
    DormitoryUpdate,
    DormitoryView,
    StudentCreate,
    StudentUpdate,
    StudentView,
)
from example.application.services import (
    DormitoryApplicationService,
    StudentApplicationService,
)

router = APIRouter()


@router.get("/students", response_model=list[StudentView])
async def list_students(service: Inject[StudentApplicationService]):
    return await service.list()


@router.get("/students/{student_id}", response_model=StudentView)
async def get_student(
    student_id: UUID,
    service: Inject[StudentApplicationService],
):
    return await service.get(student_id)


@router.post("/students", status_code=status.HTTP_201_CREATED)
async def create_student(
    command: StudentCreate,
    service: Inject[StudentApplicationService],
) -> UUID:
    return Created(await service.create(command))


@router.put("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_student(
    student_id: UUID,
    command: StudentUpdate,
    service: Inject[StudentApplicationService],
) -> Response:
    await service.update(student_id, command)
    return NoContent()


@router.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
    student_id: UUID,
    service: Inject[StudentApplicationService],
) -> Response:
    await service.delete(student_id)
    return NoContent()


@router.get("/dormitories", response_model=list[DormitoryView])
async def list_dormitories(service: Inject[DormitoryApplicationService]):
    return await service.list()


@router.get("/dormitories/{dormitory_id}", response_model=DormitoryView)
async def get_dormitory(
    dormitory_id: UUID,
    service: Inject[DormitoryApplicationService],
):
    return await service.get(dormitory_id)


@router.post("/dormitories", status_code=status.HTTP_201_CREATED)
async def create_dormitory(
    command: DormitoryCreate,
    service: Inject[DormitoryApplicationService],
) -> UUID:
    return Created(await service.create(command))


@router.put("/dormitories/{dormitory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_dormitory(
    dormitory_id: UUID,
    command: DormitoryUpdate,
    service: Inject[DormitoryApplicationService],
) -> Response:
    await service.update(dormitory_id, command)
    return NoContent()


@router.delete(
    "/dormitories/{dormitory_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_dormitory(
    dormitory_id: UUID,
    service: Inject[DormitoryApplicationService],
) -> Response:
    await service.delete(dormitory_id)
    return NoContent()


@router.put(
    "/dormitories/{dormitory_id}/students", status_code=status.HTTP_204_NO_CONTENT
)
async def assign_student(
    dormitory_id: UUID,
    command: AssignStudent,
    service: Inject[DormitoryApplicationService],
) -> Response:
    await service.assign_student(dormitory_id, command.student_id)
    return NoContent()


@router.delete(
    "/dormitories/{dormitory_id}/students/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_student(
    dormitory_id: UUID,
    student_id: UUID,
    service: Inject[DormitoryApplicationService],
) -> Response:
    await service.remove_student(dormitory_id, student_id)
    return NoContent()
