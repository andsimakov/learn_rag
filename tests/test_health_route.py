"""Tests for the health check route."""

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.api.routes.health import router

_app = FastAPI()
_app.include_router(router)
client = TestClient(_app)


def test_health_returns_200_when_db_ok(mocker):
    mocker.patch("app.api.routes.health.ping_pool", return_value=None)
    resp = client.get("/health")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {"status": "ok"}


def test_health_returns_503_when_db_unavailable(mocker):
    mocker.patch(
        "app.api.routes.health.ping_pool",
        side_effect=RuntimeError("connection refused"),
    )
    resp = client.get("/health")
    assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert resp.json()["detail"] == "Database unavailable"
