"""CORS behaviour tests for the FastAPI RAG app factory."""

from fastapi import status
from fastapi.testclient import TestClient

from app.config import Settings


def _make_client(mocker, allowed_origins: list[str]) -> TestClient:
    """Build a TestClient from create_app() with mocked settings and lifespan deps."""
    mock_settings = mocker.MagicMock(spec=Settings)
    mock_settings.allowed_origins = allowed_origins
    mocker.patch("app.main.get_settings", return_value=mock_settings)

    # Prevent lifespan from touching DB or embedder.
    mocker.patch("app.main.create_pool")
    mocker.patch("app.main.warm_up")
    mocker.patch("app.main.close_pool")

    from app.main import create_app  # import after patches are in place

    return TestClient(create_app())


def test_allowed_origin_gets_cors_header(mocker):
    client = _make_client(mocker, ["http://localhost:3000"])
    # Use a preflight OPTIONS request — CORS middleware handles it before the
    # route handler runs, so no DB pool or embedder is needed.
    resp = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == status.HTTP_200_OK
    assert "access-control-allow-origin" in resp.headers
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_disallowed_origin_gets_no_cors_header(mocker):
    client = _make_client(mocker, ["http://localhost:3000"])
    resp = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in resp.headers
