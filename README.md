# Say2Cal - Natural Language Calendar Scheduler

A CLI tool that converts natural language prompts into Google Calendar events.

## Features

- Natural language processing using Groq's Llama3-8b-8192 model
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

## Notes

- The tool uses Groq's `Llama3-8b-8192` model for natural language processing.
- The response format from Groq is expected to be a JSON object with the following structure:
  ```json
  {
    "summary": "event title",
    "start": "YYYY-MM-DDTHH:MM:SS",
    "end": "YYYY-MM-DDTHH:MM:SS",
    "timezone": "timezone"
  }
  ```

## Limitations

- The tool relies on Groq's natural language model, which may not handle ambiguous or highly complex prompts accurately.
- Timezone detection is based on user input and may not account for implicit timezone references.
- Requires an active internet connection for both Groq API and Google Calendar API.
- Only supports scheduling events in the primary Google Calendar.
- Does not currently support recurring events with complex rules (e.g., "every third Friday").

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.