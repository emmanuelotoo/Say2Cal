"""Say2Cal personal web app (Flask).

Single-user: only ALLOWED_EMAIL may sign in. The user's Google credentials live
in a signed session cookie; there is no database.
"""
import os
import json

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google.auth.exceptions import RefreshError

import core

load_dotenv()

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/userinfo.email",
]

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-insecure-key")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # Secure cookies in production; allow http on localhost for dev.
    SESSION_COOKIE_SECURE=os.getenv("OAUTHLIB_INSECURE_TRANSPORT") != "1",
)

# Relax oauthlib scope-order checks; Google may reorder/add the openid scope.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")


def allowed_email() -> str:
    return os.getenv("ALLOWED_EMAIL", "").strip().lower()


def is_allowed(email: str) -> bool:
    return bool(email) and email.strip().lower() == allowed_email()


def creds_from_session():
    """Rebuild Google Credentials from the session cookie, or None."""
    raw = session.get("credentials")
    if not raw:
        return None
    return Credentials.from_authorized_user_info(json.loads(raw), SCOPES)


@app.route("/")
def index():
    return render_template("index.html", email=session.get("email"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/parse", methods=["POST"])
def parse():
    creds = creds_from_session()
    if creds is None:
        return redirect(url_for("login"))

    prompt = request.form.get("prompt", "").strip()
    tz_name = request.form.get("timezone", "").strip()
    try:
        tz, canonical = core.resolve_timezone(tz_name)
        event_data = core.parse_event_prompt(prompt, tz)
    except core.Say2CalError as e:
        return render_template("index.html", email=session.get("email"), prompt=prompt, error=str(e))

    return render_template("preview.html", event=event_data, timezone=canonical, email=session.get("email"))


@app.route("/create", methods=["POST"])
def create():
    creds = creds_from_session()
    if creds is None:
        return redirect(url_for("login"))

    event_data = {
        "summary": request.form.get("summary", "").strip(),
        "start": request.form.get("start", "").strip(),
        "end": request.form.get("end", "").strip(),
        "recurrence": [r.strip() for r in request.form.get("recurrence", "").splitlines() if r.strip()],
    }
    tz_name = request.form.get("timezone", "").strip()

    try:
        _, canonical = core.resolve_timezone(tz_name)
        body = core.build_event_body(event_data, canonical)
        event = core.insert_event(creds, body)
    except core.Say2CalError as e:
        return render_template("preview.html", event=event_data, timezone=tz_name, error=str(e), email=session.get("email"))
    except RefreshError:
        # Stored token expired or was revoked — force a fresh sign-in.
        session.clear()
        return redirect(url_for("login"))

    # Persist possibly-refreshed credentials back to the session.
    session["credentials"] = creds.to_json()

    result = {
        "summary": event_data["summary"],
        "link": event.get("htmlLink"),
        "recurring": bool(event_data["recurrence"]),
    }
    return render_template("index.html", email=session.get("email"), result=result)


def build_flow(state=None):
    return Flow.from_client_secrets_file(
        os.getenv("GOOGLE_CLIENT_SECRETS_FILE", "credentials.json"),
        scopes=SCOPES,
        state=state,
        redirect_uri=os.getenv("OAUTH_REDIRECT_URI", "http://localhost:5000/oauth2callback"),
    )


def email_from_credentials(creds) -> str:
    """Verify the id_token and return the account email."""
    request = google_requests.Request()
    info = id_token.verify_oauth2_token(creds.id_token, request, os.getenv("GOOGLE_CLIENT_ID"))
    return info.get("email", "")


@app.route("/login")
def login():
    flow = build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    session["oauth_state"] = state
    return redirect(auth_url)


@app.route("/oauth2callback")
def oauth2callback():
    state = session.get("oauth_state")
    flow = build_flow(state=state)
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials

    email = email_from_credentials(creds)
    if not is_allowed(email):
        session.clear()
        return render_template("private.html"), 403

    session["credentials"] = creds.to_json()
    session["email"] = email
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
