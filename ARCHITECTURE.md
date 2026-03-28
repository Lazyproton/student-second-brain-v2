# 🏗️ Architecture — Student Second Brain V2

## Overview
Student Second Brain V2 is built on a modular, decoupled architecture prioritizing speed, automation, and intelligent data routing. The Chrome Extension acts as the omni-present entry point for capturing knowledge across the web, while the Flask Backend serves as the central brain orchestrating the entire system. At its core, the Notion MCP (Model Context Protocol) functions as the dynamic data layer to provision databases and write structured notes, supercharged by the OpenRouter LLM which acts as the intelligence layer to automatically summarize, tag, and categorize all incoming information.

## Component Breakdown

### 1. Chrome Extension (Frontend)
- **manifest.json** — Manages extension permissions, configures background service workers, and allows CORS integration with the local Flask server.
- **popup.html** — The interactive UI window presenting users with 5 distinct feature tabs (Capture, Subject, CP Tracker, Search, Dashboard).
- **popup.js** — Handles all click events, DOM scraping injections, and executes asynchronous `fetch()` calls to the Flask backend.
- **content.js** — A script injected into active web pages purely to detect and extract user-highlighted text.
- **background.js** — The Manifest V3 service worker responsible for managing the extension's lifecycle and background tab state detection.
- **styles.css** — Contains the sleek, dark-theme styling scoped strictly to the extension popup.

### 2. Flask Backend (API Layer)
- **POST /capture** — Accepts URL/title and selected text. Outputs a Notion page ID in the default Notes DB.
- **POST /capture/subject** — Directs captured content and an AI summary to a specific dynamically-created Subject DB.
- **POST /youtube** — Accepts a YouTube URL. Outputs a Notion page ID containing the video transcript and an AI summary.
- **POST /codeforces** — Accepts a Codeforces URL, problem name, and statement. Outputs a hint-free AI summary to the CP Tracker DB.
- **GET /query** — Accepts a natural language `q` string. Returns a list of matched pages from the Notion workspace.
- **GET /calendar** — Returns upcoming exams from the Notion Calendar DB and triggers Google Calendar sync.
- **GET /subjects** — Returns the list of all active Subject databases stored in the Master Index.
- **POST /subjects/create** — Takes a `subject_name`. Instructs Notion MCP to create a new DB and returns the new `database_id`.
- **GET /test-capture** — A simple health-check route to guarantee the local backend is reachable.

### 3. LLM Layer (llm.py)
- **Model Choice**: Uses Gemini 2.0 Flash via OpenRouter for its combination of massive context windows, ultra-fast inference speed, and free access tier.
- **Configurability**: The model name is strictly driven by the `OPENROUTER_MODEL` environment variable, enabling easy swaps to other models.
- **summarize_content()**: Maps different contextual prompts based on the content payload (webpage, youtube, pdf, codeforces) to optimize formatting and summaries.
- **search_query_to_notion_filter()**: Uses the LLM to distill natural, conversational language queries from the user into precise layout keywords for the Notion Search API.
- **Codeforces Specifics**: The Codeforces prompt is strictly constrained by a rule-set to generate constraint-focused previews while outright forbidding any algorithmic solutions or hints to preserve practice integrity.

### 4. Notion MCP Layer (notion_writer.py)
- **save_to_notes_db()** — Commits web clips and YouTube summaries to the general Student Notes database.
- **save_to_cp_tracker()** — Commits Codeforces problems with difficulty, statuses, and safe AI summaries to the CP Tracker.
- **save_to_subject_db()** — Routes captured notes directly into a targeted, dynamically generated child database.
- **create_subject_database()** — Dynamically provisions an entirely new Notion database with a standard schema under the parent page, registering its ID to the Master Index.
- **get_all_subjects()** — Queries the Master Index to list all dynamically created subject databases for the extension's dropdown UI.
- **get_subject_notes()** — Retrieves all compiled notes stored inside a specific dynamically created subject database.
- **search_notes()** — Queries the whole workspace using LLM-optimized keywords to return matched learning materials.
- **get_upcoming_exams()** — Pulls dates and exam details from the unified Notion Calendar Database.

### 5. Dynamic Subject Database System
This is the most impressive feature of the system, transforming Notion from a static table into a programmable architecture. 
- The Master Index database tracks all subject databases.
- When a user picks a new subject via the extension, Flask calls the Notion API to CREATE a new database with a predefined schema.
- This new database is created inside the designated Student Brain parent page.
- The new actual Database ID is then saved to the Master Index automatically as a reference row.
- Future captures to the same subject simply route to this stored existing database via its mapped ID.
```text
Extension (New Subject) → Flask → Notion API creates DB → DB ID saved to Master Index
```

### 6. Parsers
- **parse_youtube.py** — Extracts the video ID via RegEx, fetches the internal subtitle transcript using the YouTube Transcript API, and scrapes the actual video page title via BeautifulSoup.
- **parse_codeforces.py** — Works alongside the extension to grab problem statements via BeautifulSoup parsing and safe injection to avoid Cloudflare 403 blocks.
- **parse_pdf.py** — Extracts clean, continuous text blocks from binary PDF files using the PyMuPDF (`fitz`) engine.

### 7. Google Calendar Integration (google_calendar.py)
- **OAuth2 Authentication Flow**: Relies on a standard OAuth2 browser authentication flow triggered locally.
- **Session Management**: Automatically writes authorization payloads to `token.json` to prevent re-logins during persistent background syncs.
- **sync_exam_to_google_calendar()** — Writes unified Exam events directly to Google Calendar, attaching active push reminders to alert the user automatically on their devices.
- **get_upcoming_google_events()** — Reads future scheduled study blocks and events from Google.

## Data Flow Diagrams

**Flow 1 — Webpage Capture:**
User highlights text → clicks extension → popup.js gets selected text
→ POST /capture/subject → llm.py summarizes → notion_writer creates page
→ returns page ID → popup shows success

**Flow 2 — New Subject Creation:**
User types "Quantum Physics" → POST /subjects/create
→ notion_writer.create_subject_database() → Notion API creates new DB
→ saves DB ID to Master Index → returns DB ID → dropdown updates

**Flow 3 — Exam to Google Calendar:**
User adds exam to Notion Calendar → GET /calendar
→ notion_writer.get_upcoming_exams() → google_calendar.sync_exam_to_google_calendar()
→ Google Calendar event created with reminders → user gets phone notification

## Environment Variables Reference
- `OPENROUTER_API_KEY`: Your OpenRouter authentication key for the LLM. Acquired from openrouter.ai.
- `OPENROUTER_MODEL`: The specific LLM model identifier (e.g., `google/gemini-2.0-flash-exp:free`).
- `NOTION_TOKEN`: Internal Integration Secret from the Notion Developers portal.
- `NOTION_NOTES_DB_ID`: The 32-character ID of the default Student Notes database.
- `NOTION_CP_DB_ID`: The 32-character ID of the Codeforces CP Tracker database.
- `NOTION_CALENDAR_DB_ID`: The 32-character ID of the main Calendar/Exam database.
- `NOTION_MASTER_INDEX_DB_ID`: The 32-character ID tracking dynamic Subject Databases.
- `NOTION_PARENT_PAGE_ID`: The Notion Page ID where new dynamic Subject Databases are generated.
- `FLASK_PORT`: The local port metric to listen on (default `5000`).
- `FLASK_DEBUG`: Toggles verbose error logging if set to `True`.
- `GOOGLE_CALENDAR_CREDENTIALS`: Relative path defining where the Google `credentials.json` is stored.

## Security Notes
- All secrets stored in `.env` — never committed to GitHub
- `credentials.json` and `token.json` are gitignored
- CORS restricted to `chrome-extension://` and localhost only
- No API keys hardcoded anywhere in the codebase
