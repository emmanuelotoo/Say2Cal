from datetime import datetime, timezone, timedelta
import pytest
import core


def test_require_env_returns_value(monkeypatch):
    monkeypatch.setenv("SOME_KEY", "abc")
    assert core._require_env("SOME_KEY") == "abc"


def test_require_env_missing_raises(monkeypatch):
    monkeypatch.delenv("SOME_KEY", raising=False)
    with pytest.raises(core.Say2CalError):
        core._require_env("SOME_KEY")


def test_parse_iso_datetime_with_z_suffix():
    dt = core._parse_iso_datetime("2026-06-05T09:00:00Z", default_tz=timezone.utc)
    assert dt.tzinfo is not None
    assert dt.hour == 9


def test_parse_iso_datetime_naive_gets_default_tz():
    tz = timezone(timedelta(hours=-5))
    dt = core._parse_iso_datetime("2026-06-05T09:00:00", default_tz=tz)
    assert dt.utcoffset() == timedelta(hours=-5)


def test_parse_iso_datetime_invalid_raises():
    with pytest.raises(core.Say2CalError):
        core._parse_iso_datetime("not-a-date", default_tz=timezone.utc)


def test_resolve_timezone_valid():
    tz, name = core.resolve_timezone("America/New_York")
    assert name == "America/New_York"
    # tz must be usable to build an aware datetime
    assert datetime(2026, 6, 5, tzinfo=tz).tzinfo is not None


def test_resolve_timezone_invalid_raises():
    with pytest.raises(core.Say2CalError):
        core.resolve_timezone("Not/AZone")


def test_resolve_timezone_blank_raises():
    with pytest.raises(core.Say2CalError):
        core.resolve_timezone("")


from zoneinfo import ZoneInfo
from unittest.mock import MagicMock


def _fake_groq_response(content: str):
    """Build a stub mimicking the Groq client's chat.completions.create return."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def test_parse_event_prompt_happy_path(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    payload = (
        '{"summary": "Dentist", "start": "2026-06-06T15:30:00", '
        '"end": "2026-06-06T16:30:00", "timezone": "America/New_York", '
        '"recurrence": []}'
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_groq_response(payload)
    monkeypatch.setattr(core, "Groq", lambda api_key: fake_client)

    result = core.parse_event_prompt("dentist tomorrow at 3:30pm", ZoneInfo("America/New_York"))

    assert result["summary"] == "Dentist"
    assert result["start"] == "2026-06-06T15:30:00"
    assert result["recurrence"] == []


def test_parse_event_prompt_missing_field_raises(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    payload = '{"summary": "Dentist", "start": "2026-06-06T15:30:00"}'  # no "end"
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_groq_response(payload)
    monkeypatch.setattr(core, "Groq", lambda api_key: fake_client)

    with pytest.raises(core.Say2CalError):
        core.parse_event_prompt("dentist tomorrow", ZoneInfo("America/New_York"))


def test_parse_event_prompt_null_recurrence_becomes_list(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    payload = (
        '{"summary": "Gym", "start": "2026-06-06T07:00:00", '
        '"end": "2026-06-06T08:00:00", "recurrence": null}'
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_groq_response(payload)
    monkeypatch.setattr(core, "Groq", lambda api_key: fake_client)

    result = core.parse_event_prompt("gym", ZoneInfo("America/New_York"))
    assert result["recurrence"] == []


def test_build_event_body_basic():
    data = {
        "summary": "Dentist",
        "start": "2026-06-06T15:30:00",
        "end": "2026-06-06T16:30:00",
        "recurrence": [],
    }
    body = core.build_event_body(data, "America/New_York")
    assert body["summary"] == "Dentist"
    assert body["start"]["timeZone"] == "America/New_York"
    assert body["end"]["timeZone"] == "America/New_York"
    # normalized to include seconds
    assert body["start"]["dateTime"].startswith("2026-06-06T15:30:00")
    assert "recurrence" not in body


def test_build_event_body_includes_recurrence():
    data = {
        "summary": "Standup",
        "start": "2026-06-08T09:00:00",
        "end": "2026-06-08T09:15:00",
        "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO"],
    }
    body = core.build_event_body(data, "America/New_York")
    assert body["recurrence"] == ["RRULE:FREQ=WEEKLY;BYDAY=MO"]


def test_build_event_body_end_before_start_raises():
    data = {
        "summary": "Bad",
        "start": "2026-06-06T16:30:00",
        "end": "2026-06-06T15:30:00",
        "recurrence": [],
    }
    with pytest.raises(core.Say2CalError):
        core.build_event_body(data, "America/New_York")


def test_build_event_body_missing_summary_raises():
    data = {"start": "2026-06-06T15:30:00", "end": "2026-06-06T16:30:00", "recurrence": []}
    with pytest.raises(core.Say2CalError):
        core.build_event_body(data, "America/New_York")


def test_insert_event_calls_calendar_api(monkeypatch):
    captured = {}

    class FakeInsert:
        def execute(self):
            return {"htmlLink": "https://calendar.google.com/event?eid=abc"}

    class FakeEvents:
        def insert(self, calendarId, body):
            captured["calendarId"] = calendarId
            captured["body"] = body
            return FakeInsert()

    class FakeService:
        def events(self):
            return FakeEvents()

    monkeypatch.setattr(core, "build", lambda *a, **k: FakeService())

    body = {"summary": "Dentist"}
    result = core.insert_event(creds="fake-creds", body=body, calendar_id="primary")

    assert result["htmlLink"].startswith("https://calendar.google.com/")
    assert captured["calendarId"] == "primary"
    assert captured["body"] == body
