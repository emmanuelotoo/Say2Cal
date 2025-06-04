# Say2Cal - Natural Language Calendar Scheduler

A CLI tool that converts natural language prompts into Google Calendar events.

## Features

- Natural language processing using Groq's llama-3.1-8b-instant model
- Google Calendar integration
- Simple CLI interface
- Automatic timezone handling based on your system's local timezone
- Support for recurring events (e.g., "every Tuesday", "weekly until date")

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

     ```dotenv
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
- "Add my weekly team meeting every Monday at 10am until the end of the year"
- "Create an event for my dentist appointment next Friday at 3:30pm"
- "Schedule study session every Wednesday from 7pm to 9pm"

## Error Handling

The tool will display error messages if:

- The prompt cannot be parsed
- Google Calendar authentication fails
- The event cannot be created

## Notes

- The tool uses Groq's `llama-3.1-8b-instant` model for natural language processing.
- The response format from Groq is expected to be a JSON object with the following structure:

  ```json
  {
    "summary": "concise event title",
    "start": "YYYY-MM-DDTHH:MM:SS",
    "end": "YYYY-MM-DDTHH:MM:SS",
    "recurrence": ["RRULE:FREQ=...;..."] // Optional: List of iCalendar RRULE strings
  }
  ```

- Timezone is automatically detected from your local system.

## Limitations

- The tool relies on Groq's natural language model, which may not handle ambiguous or highly complex prompts accurately.
- Requires an active internet connection for both Groq API and Google Calendar API.
- Only supports scheduling events in the primary Google Calendar.
- Functionality for deleting events has not yet been added.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
