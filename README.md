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
  - Copy `.env.example` to `.env` and set:

     ```dotenv
     GROQ_API_KEY=your_api_key_here
     ```

## Usage

Run the scheduler with a natural language prompt:

```bash
python scheduler.py "Schedule my math class to be on Tuesday from 9:30 am to 11:00"
```

You can also run it without quotes (the CLI will join all remaining words into the prompt):

```bash
python scheduler.py Schedule my math class to be on Tuesday from 9:30 am to 11:00
```

Optional flags:

- `--dry-run` prints the parsed JSON without creating an event
- `--calendar-id` targets a non-primary calendar
- `--token-path` / `--credentials-path` override auth file locations
- `--verbose` enables debug logging

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

## Web App (personal, cloud-hosted)

Say2Cal also runs as a personal web app so you can create events from a browser
(including your phone) without the terminal. Only your Google account can sign in.

### Google Cloud setup (one time)

1. In the [Google Cloud Console](https://console.cloud.google.com/), open your project.
2. Enable the **Google Calendar API**.
3. Create an OAuth client of type **Web application** (separate from the desktop
   client used by the CLI). Download it as `credentials.json`.
4. Add authorized redirect URIs:
   - `http://localhost:5000/oauth2callback` (local dev)
   - `https://<your-app>.onrender.com/oauth2callback` (production)
5. On the OAuth consent screen, keep publishing status **Testing** and add your
   own email as a test user. (No Google verification needed for a private app.)

### Environment variables

Copy `.env.example` to `.env` and fill in: `GROQ_API_KEY`, `FLASK_SECRET_KEY`
(`python -c "import secrets; print(secrets.token_hex(32))"`), `ALLOWED_EMAIL`,
`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRETS_FILE`, `OAUTH_REDIRECT_URI`. For local
http dev only, also set `OAUTHLIB_INSECURE_TRANSPORT=1`.

### Run locally

```bash
pip install -r requirements.txt
flask --app app run --port 5000
```

Open `http://localhost:5000`, sign in with Google, type a prompt, review the
parsed event, and confirm.

### Deploy to Render

1. Push the repo to GitHub.
2. Create a new **Web Service** on [Render](https://render.com/) from the repo.
3. Start command: `gunicorn app:app` (also defined in `Procfile`).
4. Set the environment variables above in the Render dashboard. Do NOT set
   `OAUTHLIB_INSECURE_TRANSPORT`. Set `OAUTH_REDIRECT_URI` to your
   `https://<your-app>.onrender.com/oauth2callback`.
5. Provide the OAuth client secrets to the server. Either commit-free upload of
   `credentials.json` via a Render Secret File, or keep it out of git and supply
   it through your chosen secret mechanism.
6. Note: the free tier sleeps when idle and takes ~30–60s to wake on the first
   request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
