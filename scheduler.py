import os
import json
from datetime import datetime
import click
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from groq import Groq

# Load environment variables
load_dotenv()

# Google Calendar API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_google_credentials():
    """Get or refresh Google Calendar API credentials."""
    creds = None
    # The file token.json stores the user's access and refresh tokens
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return creds

def parse_event_prompt(prompt):
    """Parse natural language prompt into structured event data using Groq API."""
    client = Groq(api_key=os.getenv('GROQ_API_KEY'))
    today = datetime.now().strftime('%Y-%m-%d') # Get current date
    
    response = client.chat.completions.create(
        model="llama3-8b-8192", # Changed model name
        messages=[
            # Update system prompt to include recurrence rules in RRULE format
            {"role": "system", "content": f"You are a helpful assistant that parses natural language into calendar event data, including recurrence rules. Today's date is {today}. Return only a JSON object with the following structure: {{'summary': 'event title', 'start': 'YYYY-MM-DDTHH:MM:SS', 'end': 'YYYY-MM-DDTHH:MM:SS', 'timezone': 'timezone', 'recurrence': ['RRULE:FREQ=...;...']}}. If no recurrence is specified, return an empty list or null for 'recurrence'. Use the iCalendar RRULE format (RFC 5545). Example: 'every Tuesday until Dec 31st' -> ['RRULE:FREQ=WEEKLY;BYDAY=TU;UNTIL=YYYY1231T235959Z']"}, 
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
    service = build('calendar', 'v3', credentials=creds)
    
    event = {
        'summary': event_data['summary'],
        'start': {
            'dateTime': event_data['start'],
            'timeZone': event_data['timezone'],
        },
        'end': {
            'dateTime': event_data['end'],
            'timeZone': event_data['timezone'],
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