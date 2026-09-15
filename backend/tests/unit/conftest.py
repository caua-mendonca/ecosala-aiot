from __future__ import annotations

import pytest
from fastapi import FastAPI

from app.presentation.api.v1.routes import devices, health, readings


@pytest.fixture
def api_app() -> FastAPI:
    """App FastAPI "nua" (sem o lifespan real) para testar as rotas isoladamente.

    Nao usa app.main.create_app() de proposito: aquele monta o lifespan que
    conecta a MQTT/InfluxDB reais. Aqui montamos so os routers e cada teste
    injeta suas proprias dependencias falsas via app.dependency_overrides.
    """
    app = FastAPI()
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(devices.router, prefix="/api/v1")
    app.include_router(readings.router, prefix="/api/v1")
    return app
