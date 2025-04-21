# Say2Cal - Natural Language Calendar Scheduler

A CLI tool that converts natural language prompts into Google Calendar events.

## Features

- Natural language processing using Groq's Mixtral model
- Google Calendar integration
- Simple CLI interface
- Automatic timezone handling

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up Google Calendar API:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project
   - Enable the Google Calendar API
   - Create OAuth 2.0 credentials
   - Download the credentials and save them as `credentials.json` in the project root

3. Set up Groq API:
   - Get your API key from [Groq](https://console.groq.com/)
   - Create a `.env` file in the project root with:
     ```
     GROQ_API_KEY=your_api_key_here
     ```

## Usage

Run the scheduler with a natural language prompt:

```bash
python scheduler.py "Schedule my math class to be on Tuesday from 9:30 am to 11:00"
```

The first time you run the tool, it will open a browser window for Google Calendar authentication. After authentication, the credentials will be saved locally for future use.

## Example Prompts

- "Schedule a meeting with John tomorrow at 2pm for 1 hour"
- "Add my weekly team meeting every Monday at 10am"
- "Create an event for my dentist appointment next Friday at 3:30pm"

## Error Handling

The tool will display error messages if:
- The prompt cannot be parsed
- Google Calendar authentication fails
- The event cannot be created 