from __future__ import annotations

import pytest
from fastapi import FastAPI

from app.presentation.api.v1.routes import devices, health, readings


@pytest.fixture
def api_app() -> FastAPI:
    app = FastAPI()
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(devices.router, prefix="/api/v1")
    app.include_router(readings.router, prefix="/api/v1")
    return app
