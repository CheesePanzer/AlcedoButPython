from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from alcedo import Entity, configure_alcedo
from example.api.controllers import router
from example.infrastructure.services import add_example_services


async def test_dormitory_crud_and_student_assignment(tmp_path: Path) -> None:
    app = FastAPI()
    runtime = configure_alcedo(
        app,
        f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        metadata=Entity.metadata,
    )
    add_example_services(runtime)
    app.include_router(router, prefix="/api")

    async with runtime.engine.begin() as connection:
        await connection.run_sync(Entity.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        student_response = await client.post(
            "/api/students",
            json={"student_no": "S001", "name": "Alice"},
        )
        assert student_response.status_code == 201
        student_id = student_response.json()

        dormitory_response = await client.post(
            "/api/dormitories",
            json={"code": "A-101", "capacity": 1},
        )
        assert dormitory_response.status_code == 201
        dormitory_id = dormitory_response.json()

        assign_response = await client.put(
            f"/api/dormitories/{dormitory_id}/students",
            json={"student_id": student_id},
        )
        assert assign_response.status_code == 204

        detail_response = await client.get(f"/api/dormitories/{dormitory_id}")
        assert detail_response.status_code == 200
        assert detail_response.json()["student_ids"] == [student_id]

        too_small = await client.put(
            f"/api/dormitories/{dormitory_id}",
            json={"code": "A-101", "capacity": 0},
        )
        assert too_small.status_code == 422

        delete_student = await client.delete(f"/api/students/{student_id}")
        assert delete_student.status_code == 409
        problem = delete_student.json()
        assert delete_student.headers["content-type"].startswith(
            "application/problem+json"
        )
        assert problem["title"] == "Conflict"
        assert problem["status"] == 409
        assert problem["traceId"]

        remove_response = await client.delete(
            f"/api/dormitories/{dormitory_id}/students/{student_id}"
        )
        assert remove_response.status_code == 204

        delete_student = await client.delete(f"/api/students/{student_id}")
        assert delete_student.status_code == 204

    await runtime.engine.dispose()
