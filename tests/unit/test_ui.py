from pathlib import Path

from fastapi.testclient import TestClient
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.main import app


def test_icia_template_is_server_rendered_without_javascript() -> None:
    template_path = Path("templates/icia.html")
    source = template_path.read_text(encoding="utf-8")
    assert "<script" not in source.lower()
    environment = Environment(
        loader=FileSystemLoader(str(template_path.parent)), undefined=StrictUndefined
    )
    environment.get_template("icia.html").render(
        auth=None, active="login", error=None, notice=None, signup_enabled=False
    )


def test_ui_routes_are_registered() -> None:
    paths = set(app.openapi()["paths"])
    assert "/api/v1/ui" in paths
    assert "/api/v1/ui/dashboard" in paths
    assert "/api/v1/ui/contracts/{version_id}" in paths
    assert "/api/v1/ui/ask" in paths
    assert "/api/v1/ui/compare" in paths
    assert "/api/v1/ui/legal" in paths


def test_login_page_is_public() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/ui")
    assert response.status_code == 200
    assert "Sign in" in response.text
    assert "Indian Contract Intelligence" in response.text


def test_protected_ui_redirects_without_cookie() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/ui/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/api/v1/ui"
