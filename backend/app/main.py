from fastapi import FastAPI

from app.clients.model_client import validate_model_runtime_available
from app.api.routes.evaluations import router as evaluations_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    validate_model_runtime_available(get_settings())
    app = FastAPI(title="Requirements Evaluator API")
    app.include_router(evaluations_router)
    return app


app = create_app()
