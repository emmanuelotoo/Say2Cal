import pytest
import app as app_module


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAIL", "owner@example.com")
    app_module.app.config["TESTING"] = True
    app_module.app.secret_key = "test-secret"
    with app_module.app.test_client() as c:
        yield c
