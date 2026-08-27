from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.hosting import create_hosted_app


def test_health_response_is_typed_and_versioned() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "product": "filingscope",
        "version": "0.1.0",
        "schema_version": "1.0.0",
    }


def test_hosted_app_serves_api_before_static_ui(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ui_dir = tmp_path / "ui"
    ui_dir.mkdir()
    (ui_dir / "index.html").write_text("<h1>FilingScope hosted</h1>")
    monkeypatch.setenv("FILINGSCOPE_UI_DIR", str(ui_dir))
    monkeypatch.setenv("FILINGSCOPE_DATA_DIR", str(tmp_path / "data"))

    hosted = TestClient(create_hosted_app())
    assert hosted.get("/health").status_code == 200
    assert "FilingScope hosted" in hosted.get("/").text
