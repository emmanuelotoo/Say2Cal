def test_parse_requires_login(client):
    resp = client.post("/parse", data={"prompt": "hi", "timezone": "UTC"})
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_index_shows_sign_in_when_logged_out(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Sign in with Google" in resp.data


from unittest.mock import MagicMock
import app as app_module


def test_login_redirects_to_google(client, monkeypatch):
    fake_flow = MagicMock()
    fake_flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth?x=1", "state123")
    monkeypatch.setattr(app_module, "build_flow", lambda **kw: fake_flow)

    resp = client.get("/login")
    assert resp.status_code == 302
    assert "accounts.google.com" in resp.headers["Location"]


def test_callback_rejects_wrong_email(client, monkeypatch):
    fake_creds = MagicMock()
    fake_flow = MagicMock()
    fake_flow.credentials = fake_creds
    monkeypatch.setattr(app_module, "build_flow", lambda **kw: fake_flow)
    monkeypatch.setattr(app_module, "email_from_credentials", lambda creds: "intruder@example.com")

    with client.session_transaction() as sess:
        sess["oauth_state"] = "state123"

    resp = client.get("/oauth2callback?state=state123&code=abc")
    assert resp.status_code == 403
    assert b"private" in resp.data.lower()


def test_callback_accepts_allowed_email(client, monkeypatch):
    fake_creds = MagicMock()
    fake_creds.to_json.return_value = '{"token": "x"}'
    fake_flow = MagicMock()
    fake_flow.credentials = fake_creds
    monkeypatch.setattr(app_module, "build_flow", lambda **kw: fake_flow)
    monkeypatch.setattr(app_module, "email_from_credentials", lambda creds: "owner@example.com")

    with client.session_transaction() as sess:
        sess["oauth_state"] = "state123"

    resp = client.get("/oauth2callback?state=state123&code=abc")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


def test_parse_renders_preview(client, monkeypatch):
    monkeypatch.setattr(app_module, "creds_from_session", lambda: MagicMock())
    monkeypatch.setattr(
        app_module.core,
        "parse_event_prompt",
        lambda prompt, tz: {
            "summary": "Dentist",
            "start": "2026-06-06T15:30:00",
            "end": "2026-06-06T16:30:00",
            "recurrence": [],
        },
    )

    resp = client.post("/parse", data={"prompt": "dentist", "timezone": "America/New_York"})
    assert resp.status_code == 200
    assert b"Confirm event" in resp.data
    assert b"Dentist" in resp.data
    assert b"2026-06-06T15:30" in resp.data


def test_parse_bad_timezone_shows_error(client, monkeypatch):
    monkeypatch.setattr(app_module, "creds_from_session", lambda: MagicMock())
    with client.session_transaction() as sess:
        sess["email"] = "owner@example.com"
    resp = client.post("/parse", data={"prompt": "dentist", "timezone": "Not/AZone"})
    assert resp.status_code == 200
    assert b"Unknown timezone" in resp.data


def test_create_renders_confirmation(client, monkeypatch):
    fake_creds = MagicMock()
    fake_creds.to_json.return_value = '{"token": "x"}'
    monkeypatch.setattr(app_module, "creds_from_session", lambda: fake_creds)
    monkeypatch.setattr(
        app_module.core,
        "insert_event",
        lambda creds, body, calendar_id="primary": {"htmlLink": "https://calendar.google.com/e/abc"},
    )
    with client.session_transaction() as sess:
        sess["email"] = "owner@example.com"

    resp = client.post("/create", data={
        "summary": "Dentist",
        "start": "2026-06-06T15:30",
        "end": "2026-06-06T16:30",
        "recurrence": "",
        "timezone": "America/New_York",
    })
    assert resp.status_code == 200
    assert b"Created" in resp.data
    assert b"calendar.google.com" in resp.data


def test_create_end_before_start_reshows_preview(client, monkeypatch):
    monkeypatch.setattr(app_module, "creds_from_session", lambda: MagicMock())

    resp = client.post("/create", data={
        "summary": "Dentist",
        "start": "2026-06-06T16:30",
        "end": "2026-06-06T15:30",
        "recurrence": "",
        "timezone": "America/New_York",
    })
    assert resp.status_code == 200
    assert b"Confirm event" in resp.data
    assert b"after the start time" in resp.data


def test_create_requires_login(client, monkeypatch):
    monkeypatch.setattr(app_module, "creds_from_session", lambda: None)
    resp = client.post("/create", data={"summary": "x", "start": "2026-06-06T16:30",
                                         "end": "2026-06-06T17:30", "timezone": "UTC"})
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_create_refresh_failure_redirects_to_login(client, monkeypatch):
    from google.auth.exceptions import RefreshError
    monkeypatch.setattr(app_module, "creds_from_session", lambda: MagicMock())

    def boom(creds, body, calendar_id="primary"):
        raise RefreshError("token revoked")

    monkeypatch.setattr(app_module.core, "insert_event", boom)
    resp = client.post("/create", data={
        "summary": "Dentist", "start": "2026-06-06T15:30", "end": "2026-06-06T16:30",
        "recurrence": "", "timezone": "America/New_York",
    })
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
