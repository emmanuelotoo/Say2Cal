import logging
from pathlib import Path

import click
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from tzlocal import get_localzone

import core

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar"]
LOG = logging.getLogger(__name__)


def get_google_credentials(token_path: Path, credentials_path: Path):
    """Get or refresh Google Calendar API credentials (desktop OAuth flow)."""
    creds = None
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except ValueError:
            LOG.warning("Error reading token file. Re-authenticating: %s", token_path)
            token_path.unlink(missing_ok=True)
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as e:
                LOG.warning("Failed to refresh token (%s). Re-authenticating.", e)
                token_path.unlink(missing_ok=True)
                creds = None
            except Exception as e:
                LOG.warning("Unexpected error during token refresh (%s).", e)
                token_path.unlink(missing_ok=True)
                creds = None

        if not creds:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)
                token_path.parent.mkdir(parents=True, exist_ok=True)
                with token_path.open("w", encoding="utf-8") as token:
                    token.write(creds.to_json())
            except Exception as e:
                raise click.ClickException(f"Error during Google authentication flow: {e}") from e

    return creds


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("prompt", nargs=-1, required=True)
@click.option("--calendar-id", default="primary", show_default=True, help="Target Google Calendar ID.")
@click.option("--token-path", default="token.json", show_default=True, help="Path to token JSON file.")
@click.option("--credentials-path", default="credentials.json", show_default=True, help="Path to OAuth credentials JSON file.")
@click.option("--dry-run", is_flag=True, help="Parse only; do not create the calendar event.")
@click.option("--verbose", is_flag=True, help="Enable debug logging.")
def main(prompt, calendar_id, token_path, credentials_path, dry_run, verbose):
    """Schedule an event in Google Calendar based on a natural language prompt."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(levelname)s: %(message)s")

    prompt_text = " ".join(prompt).strip()
    if not prompt_text:
        raise click.ClickException("Prompt cannot be empty.")

    local_tz = get_localzone()
    tz_name = str(local_tz)

    try:
        event_data = core.parse_event_prompt(prompt_text, local_tz)

        if dry_run:
            import json
            click.echo(json.dumps(event_data, indent=2))
            return

        body = core.build_event_body(event_data, tz_name)
        creds = get_google_credentials(token_path=Path(token_path), credentials_path=Path(credentials_path))
        event = core.insert_event(creds, body, calendar_id=calendar_id)

        start = body["start"]["dateTime"]
        end = body["end"]["dateTime"]
        recurrence_info = " (recurring)" if event_data.get("recurrence") else ""
        html_link = event.get("htmlLink")
        link_info = f"\nLink: {html_link}" if html_link else ""
        click.echo(
            f"Event '{event_data['summary']}' scheduled: {start} to {end}"
            f"{recurrence_info}.{link_info}"
        )
    except core.Say2CalError as e:
        raise click.ClickException(str(e)) from e
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(str(e)) from e


if __name__ == "__main__":
    main()
