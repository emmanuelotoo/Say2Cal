import os
import json
import logging
from pathlib import Path
from datetime import datetime
import click
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from groq import Groq
from google.auth.exceptions import RefreshError
from tzlocal import get_localzone

# Load environment variables
load_dotenv()

# Google Calendar API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar']

LOG = logging.getLogger(__name__)


def _parse_iso_datetime(value: str, default_tz):
    """Parse ISO datetime, accepting 'Z' and naive values.

    If timezone info is missing, default_tz is attached.
    """
    if not isinstance(value, str) or not value.strip():
        raise click.ClickException("Invalid datetime value returned by parser.")
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as e:
        raise click.ClickException(f"Invalid datetime format returned by parser: {value}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=default_tz)
    return dt


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise click.ClickException(f"Missing required environment variable: {name}. Set it in .env or your shell.")
    return value

def get_google_credentials(token_path: Path, credentials_path: Path):
    """Get or refresh Google Calendar API credentials."""
    creds = None
    # The file token.json stores the user's access and refresh tokens
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except ValueError:
            # Handle case where token.json is corrupted
            LOG.warning("Error reading token file. Deleting and re-authenticating: %s", token_path)
            token_path.unlink(missing_ok=True)
            creds = None
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as e:
                # If refresh fails (e.g., token revoked), delete token and re-authenticate
                LOG.warning("Failed to refresh token (%s). Deleting token and re-authenticating.", e)
                token_path.unlink(missing_ok=True)
                creds = None # Ensure re-authentication flow is triggered
            except Exception as e: # Catch other potential errors during refresh
                LOG.warning("Unexpected error during token refresh (%s). Re-authenticating.", e)
                token_path.unlink(missing_ok=True)
                creds = None
        
        # This block will now run if creds is None initially, 
        # or if creds became None after a failed refresh.
        if not creds: 
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)
                # Save the credentials for the next run
                token_path.parent.mkdir(parents=True, exist_ok=True)
                with token_path.open('w', encoding='utf-8') as token:
                    token.write(creds.to_json())
            except Exception as e:
                raise click.ClickException(f"Error during Google authentication flow: {e}") from e
    
    return creds

def parse_event_prompt(prompt):
    """Parse natural language prompt into structured event data using Groq API."""
    api_key = _require_env('GROQ_API_KEY')
    client = Groq(api_key=api_key)
    local_tz = get_localzone()
    now = datetime.now(local_tz) # Get current datetime
    today_date = now.strftime('%Y-%m-%d') # Format date
    today_day_name = now.strftime('%A') # Get day name (e.g., 'Tuesday')
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant", # Updated to recommended replacement model
        messages=[
            # Update system prompt to guide summary generation and exclude date/time from it
            # Also added explicit instruction for relative date calculation.
            # Further refined relative date instruction.
            {"role": "system", "content": f"You are a helpful assistant that parses natural language into calendar event data, including recurrence rules. Today is {today_day_name}, {today_date}. Calculate future dates relative to the current date. When a day name like 'Saturday' is mentioned, find the date of the *next* occurrence of that day, starting from tomorrow. For example, if today is Thursday and the prompt mentions 'Saturday', the date should be for the upcoming Saturday (two days later). Extract the core event information. The 'summary' should be a concise description of the event's subject or action, DO NOT include date or time details in the summary. Return only a JSON object with the following structure: {{'summary': 'concise event title', 'start': 'YYYY-MM-DDTHH:MM:SS', 'end': 'YYYY-MM-DDTHH:MM:SS', 'timezone': 'timezone', 'recurrence': ['RRULE:FREQ=...;...']}}. If no recurrence is specified, return an empty list or null for 'recurrence'. Use the iCalendar RRULE format (RFC 5545). Example prompt 'Text Daquiver on Friday at 1pm' should result in a summary like 'Text Daquiver'. Example prompt 'Meeting with team every Tuesday until Dec 31st' should result in summary 'Meeting with team' and recurrence ['RRULE:FREQ=WEEKLY;BYDAY=TU;UNTIL=YYYY1231T235959Z']."},
            {"role": "user", "content": prompt}
        ],
        response_format={ "type": "json_object" }
    )
    
    parsed_content = json.loads(response.choices[0].message.content)

    # Validate minimum required fields
    for field in ("summary", "start", "end"):
        if field not in parsed_content or not parsed_content[field]:
            raise click.ClickException(f"Model response missing required field: {field}")

    # Ensure recurrence is always a list, even if null or missing in response
    if 'recurrence' not in parsed_content or parsed_content['recurrence'] is None:
        parsed_content['recurrence'] = []
    return parsed_content

def create_calendar_event(event_data, calendar_id: str, token_path: Path, credentials_path: Path):
    """Create an event in Google Calendar."""
    creds = get_google_credentials(token_path=token_path, credentials_path=credentials_path)
    service = build('calendar', 'v3', credentials=creds)

    # Get local timezone
    local_tz = get_localzone()
    local_tz_name = str(local_tz) # Convert to string (IANA name)

    # Validate times before sending to Google
    start_dt = _parse_iso_datetime(event_data['start'], default_tz=local_tz)
    end_dt = _parse_iso_datetime(event_data['end'], default_tz=local_tz)
    if end_dt <= start_dt:
        raise click.ClickException("Event end time must be after start time.")

    event = {
        'summary': event_data['summary'],
        'start': {
            'dateTime': event_data['start'],
            'timeZone': local_tz_name, # Use detected local timezone
        },
        'end': {
            'dateTime': event_data['end'],
            'timeZone': local_tz_name, # Use detected local timezone
        },
    }
    
    # Add recurrence rule if present and not empty
    if 'recurrence' in event_data and event_data['recurrence']:
        event['recurrence'] = event_data['recurrence']
    
    event = service.events().insert(calendarId=calendar_id, body=event).execute()
    return event

@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument('prompt', nargs=-1, required=True)
@click.option('--calendar-id', default='primary', show_default=True, help='Target Google Calendar ID.')
@click.option('--token-path', default='token.json', show_default=True, help='Path to token JSON file.')
@click.option('--credentials-path', default='credentials.json', show_default=True, help='Path to OAuth credentials JSON file.')
@click.option('--dry-run', is_flag=True, help='Parse only; do not create the calendar event.')
@click.option('--verbose', is_flag=True, help='Enable debug logging.')
def main(prompt, calendar_id, token_path, credentials_path, dry_run, verbose):
    """Schedule an event in Google Calendar based on a natural language prompt."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(levelname)s: %(message)s")

    prompt_text = " ".join(prompt).strip()
    if not prompt_text:
        raise click.ClickException("Prompt cannot be empty.")

    try:
        # Parse the prompt into structured event data
        event_data = parse_event_prompt(prompt_text)

        if dry_run:
            click.echo(json.dumps(event_data, indent=2))
            return
        
        # Create the event in Google Calendar
        event = create_calendar_event(
            event_data,
            calendar_id=calendar_id,
            token_path=Path(token_path),
            credentials_path=Path(credentials_path),
        )
        
        # Format the confirmation message
        local_tz = get_localzone()
        start_time = _parse_iso_datetime(event_data['start'], default_tz=local_tz).astimezone(local_tz)
        end_time = _parse_iso_datetime(event_data['end'], default_tz=local_tz).astimezone(local_tz)
        
        # Add recurrence info to confirmation if applicable
        recurrence_info = " (recurring)" if event_data.get('recurrence') else ""

        html_link = event.get('htmlLink')
        link_info = f"\nLink: {html_link}" if html_link else ""
        click.echo(
            f"Event '{event_data['summary']}' scheduled on {start_time.strftime('%Y-%m-%d')} "
            f"from {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}{recurrence_info}.{link_info}"
        )
    
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(str(e)) from e

if __name__ == '__main__':
    main()