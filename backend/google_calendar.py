# Google Calendar API integration — handles OAuth2 auth and calendar event operations

import os
from typing import Optional
from datetime import datetime, timedelta, timezone

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
except ImportError:
    raise ImportError(
        "Google Calendar libraries are not installed. Run:\n"
        "  pip install google-auth-oauthlib google-api-python-client"
    )

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Paths relative to this file so they work regardless of where the app is launched from
_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(_DIR, "credentials.json")
TOKEN_FILE = os.path.join(_DIR, "token.json")


# ── 1. get_google_calendar_service ────────────────────────────────────────────
# Handles the full OAuth2 flow: loads an existing token if available, refreshes
# it automatically if expired, or launches a browser login if no token exists.
# Saves the token to token.json after a successful login so future runs are silent.
def get_google_calendar_service():
    """
    Authenticates with Google Calendar via OAuth2 and returns the service object.

    - On first run: opens a browser window for the user to authorise the app.
    - Subsequent runs: loads token.json and refreshes silently if expired.
    - credentials.json and token.json are gitignored and must never be committed.

    Returns:
        googleapiclient.discovery.Resource: Authenticated Calendar service, or None on error.
    """
    try:
        creds = None

        # Load existing token if present
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        # Refresh or re-authorise as needed
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(CREDENTIALS_FILE):
                    raise FileNotFoundError(
                        f"credentials.json not found at {CREDENTIALS_FILE}. "
                        "Download it from Google Cloud Console → APIs & Services → Credentials."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)

            # Persist token for next run
            with open(TOKEN_FILE, "w") as token_file:
                token_file.write(creds.to_json())

        return build("calendar", "v3", credentials=creds)

    except Exception as e:
        print(f"[google_calendar] get_google_calendar_service error: {e}")
        return None


# ── 2. sync_exam_to_google_calendar ──────────────────────────────────────────
# Creates an all-day exam event on the given date in the user's primary Google
# Calendar, with an email reminder 1 day before and a popup reminder 2 hours before.
def sync_exam_to_google_calendar(exam_name: str, date: str, subject: str = "") -> Optional[str]:
    """
    Creates a Google Calendar event for an upcoming exam.

    Args:
        exam_name (str): Name of the exam.
        date      (str): Date in "YYYY-MM-DD" format.
        subject   (str): Optional subject / course name.

    Returns:
        str: The created Google Calendar event ID, or None on error.
    """
    try:
        service = get_google_calendar_service()
        if not service:
            return None

        title = f"Exam: {exam_name}"
        if subject:
            title += f" — {subject}"

        event = {
            "summary": title,
            "start":   {"date": date},       # All-day event
            "end":     {"date": date},
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email",  "minutes": 1440},   # 1 day before
                    {"method": "popup",  "minutes": 120},    # 2 hours before
                ],
            },
        }

        created = service.events().insert(calendarId="primary", body=event).execute()
        print(f"[google_calendar] Event created: {created.get('htmlLink')}")
        return created.get("id")

    except Exception as e:
        print(f"[google_calendar] sync_exam_to_google_calendar error: {e}")
        return None


# ── 3. get_upcoming_google_events ────────────────────────────────────────────
# Fetches up to 10 calendar events from today through the specified number of
# days ahead, returning each event's title, date, and event ID.
def get_upcoming_google_events(days_ahead: int = 7) -> list:
    """
    Returns upcoming events from the user's primary Google Calendar.

    Args:
        days_ahead (int): How many days into the future to look (default: 7).

    Returns:
        list[dict]: Up to 10 events with "title", "date", "event_id" keys.
                    Returns an empty list on error.
    """
    try:
        service = get_google_calendar_service()
        if not service:
            return []

        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=days_ahead)).isoformat()

        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                maxResults=10,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = []
        for item in result.get("items", []):
            start = item.get("start", {})
            # All-day events use "date"; timed events use "dateTime"
            raw_date = start.get("date") or start.get("dateTime", "")
            events.append({
                "title":    item.get("summary", "Untitled"),
                "date":     raw_date[:10],     # Trim to YYYY-MM-DD
                "event_id": item.get("id", ""),
            })

        return events

    except Exception as e:
        print(f"[google_calendar] get_upcoming_google_events error: {e}")
        return []
