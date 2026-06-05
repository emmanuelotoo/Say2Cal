"""Framework-agnostic logic shared by the Say2Cal CLI and web app.

Nothing in this module imports a web framework or `click`; surfaces translate
`Say2CalError` into their own error presentation.
"""
import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from googleapiclient.discovery import build
from groq import Groq


class Say2CalError(Exception):
    """A user-facing error with a message safe to display to the end user."""


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise Say2CalError(f"Missing required environment variable: {name}.")
    return value


def _parse_iso_datetime(value: str, default_tz):
    """Parse an ISO datetime, accepting a trailing 'Z' and naive values.

    If timezone info is missing, ``default_tz`` is attached.
    """
    if not isinstance(value, str) or not value.strip():
        raise Say2CalError("Invalid datetime value.")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise Say2CalError(f"Invalid datetime format: {value}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=default_tz)
    return dt


def resolve_timezone(tz_name: str):
    """Resolve an IANA timezone name to ``(tzinfo, canonical_name)``.

    Raises Say2CalError if the name is blank or unknown. Used to validate the
    untrusted timezone string the browser submits.
    """
    if not isinstance(tz_name, str) or not tz_name.strip():
        raise Say2CalError("Missing timezone.")
    try:
        return ZoneInfo(tz_name), tz_name
    except (ZoneInfoNotFoundError, ValueError) as e:
        raise Say2CalError(f"Unknown timezone: {tz_name}") from e


def parse_event_prompt(prompt: str, tz) -> dict:
    """Parse a natural-language prompt into structured event data via Groq.

    ``tz`` is a tzinfo used to compute "today" for relative-date resolution.
    The caller supplies it (browser timezone for web, system zone for CLI).
    """
    if not prompt or not prompt.strip():
        raise Say2CalError("Prompt cannot be empty.")

    api_key = _require_env("GROQ_API_KEY")
    client = Groq(api_key=api_key)
    now = datetime.now(tz)
    today_date = now.strftime("%Y-%m-%d")
    today_day_name = now.strftime("%A")

    system_prompt = (
        "You are a helpful assistant that parses natural language into calendar "
        "event data, including recurrence rules. Today is "
        f"{today_day_name}, {today_date}. Calculate future dates relative to the "
        "current date. When a day name like 'Saturday' is mentioned, find the date "
        "of the *next* occurrence of that day, starting from tomorrow. Extract the "
        "core event information. The 'summary' should be a concise description of "
        "the event's subject or action; DO NOT include date or time details in the "
        "summary. Return only a JSON object with the structure: {'summary': "
        "'concise event title', 'start': 'YYYY-MM-DDTHH:MM:SS', 'end': "
        "'YYYY-MM-DDTHH:MM:SS', 'timezone': 'timezone', 'recurrence': "
        "['RRULE:FREQ=...;...']}. If no recurrence is specified, return an empty "
        "list or null for 'recurrence'. Use the iCalendar RRULE format (RFC 5545)."
    )

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    try:
        parsed = json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, AttributeError, IndexError) as e:
        raise Say2CalError("Could not understand the response from the parser.") from e

    for field in ("summary", "start", "end"):
        if field not in parsed or not parsed[field]:
            raise Say2CalError(f"The parser did not return a required field: {field}.")

    if "recurrence" not in parsed or parsed["recurrence"] is None:
        parsed["recurrence"] = []
    return parsed


def build_event_body(event_data: dict, tz_name: str) -> dict:
    """Validate event data and assemble the Google Calendar event body.

    ``tz_name`` is the canonical IANA timezone name used for the event's start
    and end. Raises Say2CalError if required fields are missing or end <= start.
    """
    summary = (event_data.get("summary") or "").strip()
    if not summary:
        raise Say2CalError("Event title (summary) is required.")

    tz, _ = resolve_timezone(tz_name)
    start_dt = _parse_iso_datetime(event_data.get("start", ""), default_tz=tz)
    end_dt = _parse_iso_datetime(event_data.get("end", ""), default_tz=tz)
    if end_dt <= start_dt:
        raise Say2CalError("Event end time must be after the start time.")

    body = {
        "summary": summary,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": tz_name},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": tz_name},
    }

    recurrence = event_data.get("recurrence")
    if recurrence:
        body["recurrence"] = recurrence
    return body


def insert_event(creds, body: dict, calendar_id: str = "primary") -> dict:
    """Insert an assembled event body into Google Calendar; return the event."""
    service = build("calendar", "v3", credentials=creds)
    return service.events().insert(calendarId=calendar_id, body=body).execute()
