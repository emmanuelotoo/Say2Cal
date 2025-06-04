import os
import json
from datetime import datetime, date
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

def get_google_credentials():
    """Get or refresh Google Calendar API credentials."""
    creds = None
    token_path = 'token.json'
    # The file token.json stores the user's access and refresh tokens
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except ValueError:
            # Handle case where token.json is corrupted
            print("Error reading token.json. Deleting and re-authenticating.")
            os.remove(token_path)
            creds = None
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as e:
                # If refresh fails (e.g., token revoked), delete token and re-authenticate
                print(f"Failed to refresh token: {e}. Deleting token file and re-authenticating.")
                os.remove(token_path)
                creds = None # Ensure re-authentication flow is triggered
            except Exception as e: # Catch other potential errors during refresh
                print(f"An unexpected error occurred during token refresh: {e}. Re-authenticating.")
                if os.path.exists(token_path):
                    os.remove(token_path)
                creds = None
        
        # This block will now run if creds is None initially, 
        # or if creds became None after a failed refresh.
        if not creds: 
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
                # Save the credentials for the next run
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                print(f"Error during authentication flow: {e}")
                return None # Indicate failure to get credentials
    
    return creds

def parse_event_prompt(prompt):
    """Parse natural language prompt into structured event data using Groq API."""
    client = Groq(api_key=os.getenv('GROQ_API_KEY'))
    now = datetime.now() # Get current datetime
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
    # Ensure recurrence is always a list, even if null or missing in response
    if 'recurrence' not in parsed_content or parsed_content['recurrence'] is None:
        parsed_content['recurrence'] = []
    return parsed_content

def create_calendar_event(event_data):
    """Create an event in Google Calendar."""
    creds = get_google_credentials()
    if not creds: # Handle case where credentials could not be obtained
        raise Exception("Could not obtain Google credentials.")
    service = build('calendar', 'v3', credentials=creds)

    # Get local timezone
    local_tz = get_localzone()
    local_tz_name = str(local_tz) # Convert to string (IANA name)

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
    
    event = service.events().insert(calendarId='primary', body=event).execute()
    return event

@click.command()
@click.argument('prompt')
def main(prompt):
    """Schedule an event in Google Calendar based on a natural language prompt."""
    try:
        # Parse the prompt into structured event data
        event_data = parse_event_prompt(prompt)
        
        # Create the event in Google Calendar
        event = create_calendar_event(event_data)
        
        # Format the confirmation message
        start_time = datetime.fromisoformat(event_data['start'].replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(event_data['end'].replace('Z', '+00:00'))
        
        # Add recurrence info to confirmation if applicable
        recurrence_info = " (recurring)" if event_data.get('recurrence') else ""
        
        click.echo(f"✅ Event '{event_data['summary']}' scheduled on {start_time.strftime('%Y-%m-%d')} from {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}{recurrence_info}.")
    
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)

if __name__ == '__main__':
    main()