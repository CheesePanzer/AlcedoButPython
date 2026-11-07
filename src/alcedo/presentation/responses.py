from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from starlette import status


def Ok(content: Any = None) -> Response:
    if content is None:
        return Response(status_code=status.HTTP_200_OK)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(content),
    )


def Created(content: Any = None) -> Response:
    if content is None:
        return Response(status_code=status.HTTP_201_CREATED)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=jsonable_encoder(content),
    )


def NoContent() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def NotFound(detail: str = "resource not found") -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": detail},
    )
