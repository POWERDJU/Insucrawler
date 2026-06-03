from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app
from app.services.company_logo_service import CompanyLogoService


def test_company_logo_service_finds_life_and_nonlife_logos(tmp_path, monkeypatch):
    life_dir = tmp_path / "LOGO" / "LIFE"
    nonlife_dir = tmp_path / "LOGO" / "NONLIFE"
    life_dir.mkdir(parents=True)
    nonlife_dir.mkdir(parents=True)
    (life_dir / "삼성 생명.png").write_bytes(b"life")
    (nonlife_dir / "DB손해보험.jpg").write_bytes(b"nonlife")
    monkeypatch.setenv("COMPANY_LOGO_LIFE_DIR", str(life_dir))
    monkeypatch.setenv("COMPANY_LOGO_NONLIFE_DIR", str(nonlife_dir))
    service = CompanyLogoService()
    service.refresh_logo_index()

    assert service.get_logo_path("삼성생명", "생명보험") == (life_dir / "삼성 생명.png").resolve()
    assert service.get_logo_path("DB 손해 보험", "손해보험") == (nonlife_dir / "DB손해보험.jpg").resolve()
    logo_url = service.get_logo_url("삼성생명", "생명보험")
    assert logo_url is not None
    assert logo_url.startswith("/api/company-logos/file/life/%EC%82%BC%EC%84%B1%20%EC%83%9D%EB%AA%85.png?v=")
    assert service.get_logo_url("없는회사", "생명보험") is None


def test_company_logo_file_route_blocks_path_traversal(tmp_path, monkeypatch):
    life_dir = tmp_path / "LOGO" / "LIFE"
    nonlife_dir = tmp_path / "LOGO" / "NONLIFE"
    life_dir.mkdir(parents=True)
    nonlife_dir.mkdir(parents=True)
    (life_dir / "삼성생명.png").write_bytes(b"logo")
    monkeypatch.setenv("COMPANY_LOGO_LIFE_DIR", str(life_dir))
    monkeypatch.setenv("COMPANY_LOGO_NONLIFE_DIR", str(nonlife_dir))
    CompanyLogoService().refresh_logo_index()

    client = TestClient(app)
    payload = client.get("/api/company-logos", params={"company_name": "삼성생명", "insurance_type": "생명보험"}).json()
    assert payload["found"] is True
    assert "%EC%82%BC%EC%84%B1%EC%83%9D%EB%AA%85.png?v=" in payload["logo_url"]
    assert client.get(payload["logo_url"]).status_code == 200
    assert client.get("/api/company-logos/file/life/..%2Fsecret.png").status_code == 404
    assert client.get("/api/company-logos/file/life/secret.exe").status_code == 404
