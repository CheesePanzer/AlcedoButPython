from pathlib import Path

from fastapi import FastAPI

from alcedo import Configuration, configure_alcedo
from example.api.controllers import router
from example.infrastructure.services import add_example_services
from example.settings import DormitoryOptions

app = FastAPI(title="Alcedo dormitory example")

# The framework's database, request scope, schema and shutdown setup is one call.
configuration = Configuration.load(Path(__file__).parent)
runtime = configure_alcedo(app, configuration=configuration)
runtime.options.add(DormitoryOptions, "dormitory")
add_example_services(runtime)

app.include_router(router, prefix="/api")
