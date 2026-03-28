# AGENTS.md — Student Second Brain V2

> This file is the primary reference for AI agents working on this codebase.
> Read it fully before making any changes.

---

## Project Overview

**Student Second Brain V2** is a Chrome extension that lets students capture web content, YouTube transcripts, Codeforces problems, emails, and meeting notes directly into Notion with a single click. A Flask backend handles all processing logic, an OpenRouter LLM generates summaries and tags, and all Notion reads/writes go through the Notion MCP server.

**Core user flow:**
1. Student visits a webpage, YouTube video, or Codeforces problem.
2. They click the extension popup and hit a capture button.
3. The extension sends the page URL / selected text to the Flask backend.
4. The backend parses the content, calls the LLM for a summary, and writes a structured entry to the correct Notion database.

---

## Architecture

```
Chrome Extension (popup.js / content.js)
        │
        │  HTTP POST/GET — localhost:5000
        ▼
Flask Backend (app.py)
        │
        ├──► llm.py ──────────────► OpenRouter API (Gemini 2.0 Flash)
        │
        └──► notion_writer.py ────► Notion MCP Server ────► Notion Databases
                    │
                    └──► parsers/
                              ├── parse_youtube.py
                              ├── parse_pdf.py
                              └── parse_codeforces.py
```

---

## File Purposes

### Root

| File | Purpose |
|------|---------|
| `.env` | Real secrets (API keys, DB IDs). Never committed to git. |
| `.env.example` | Template listing all required environment variables with placeholder values. Committed to git. |
| `.gitignore` | Ensures `.env`, `__pycache__`, `.DS_Store`, and other generated files are never committed. |
| `requirements.txt` | All Python dependencies needed to run the backend. |
| `AGENTS.md` | This file. Read by AI agents before touching the codebase. |
| `README.md` | Human-facing setup guide and project description. |

### `extension/`

| File | Purpose |
|------|---------|
| `manifest.json` | Chrome Extension Manifest V3 config — declares permissions, content scripts, popup, background service worker, and host permissions for `localhost:5000`. |
| `popup.html` | The HTML structure for the extension popup window. Imports `styles.css` and `popup.js`. |
| `popup.js` | Handles all button click logic in the popup. Sends `fetch()` requests to the Flask backend. Receives selected text from `content.js` via `chrome.runtime` messaging. |
| `content.js` | Injected into every webpage. Listens for messages from `popup.js`, reads `window.getSelection()`, and returns the selected text and current URL back to the popup. |
| `background.js` | Manifest V3 service worker. Manages extension lifecycle events and can relay messages between content scripts and the popup if needed. |
| `styles.css` | All CSS for the popup UI. Scoped to the popup window only — no impact on host pages. |

### `backend/`

| File | Purpose |
|------|---------|
| `app.py` | Flask application entry point. Defines all API routes and wires together the parsers, `llm.py`, and `notion_writer.py`. Enables CORS on all routes. |
| `llm.py` | Single module responsible for all OpenRouter API calls. Exposes helper functions like `summarise(text)` and `generate_tags(text)`. No other file calls OpenRouter directly. |
| `notion_writer.py` | Single module responsible for all Notion read and write operations via the `notion-client` library and Notion MCP. No other file calls Notion directly. |

### `backend/parsers/`

| File | Purpose |
|------|---------|
| `__init__.py` | Makes `parsers` a Python package. May expose a unified `parse(url)` dispatcher in the future. |
| `parse_youtube.py` | Given a YouTube video URL, fetches the full transcript using `youtube-transcript-api` and returns clean text. |
| `parse_pdf.py` | Given a PDF file path or binary blob, extracts all readable text using PyMuPDF (`fitz`). |
| `parse_codeforces.py` | Given a Codeforces problem URL, scrapes the problem statement, constraints, and examples using `BeautifulSoup4`. |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Chrome Extension | HTML5, CSS3, Vanilla JavaScript — no frameworks |
| Backend runtime | Python 3.10+ |
| Web framework | Flask + `flask-cors` |
| LLM | OpenRouter API — model: `google/gemini-2.0-flash-exp:free` |
| Notion integration | `notion-client` Python library + Notion MCP server |
| YouTube parsing | `youtube-transcript-api` |
| PDF parsing | `PyMuPDF` (imported as `fitz`) |
| Web scraping | `requests` + `BeautifulSoup4` |
| Config management | `python-dotenv` (reads `.env` at startup) |

---

## API Endpoints (Flask)

All endpoints are served at `http://localhost:5000` (or the port set in `FLASK_PORT`).

### `POST /capture`
Saves a webpage URL or selected text snippet to the **Student Notes** database.

**Request body (JSON):**
```json
{
  "url": "https://example.com/article",
  "selected_text": "Optional highlighted text from the page",
  "title": "Page title"
}
```
**Response:** `{ "success": true, "notion_page_id": "..." }`

---

### `POST /youtube`
Fetches the transcript of a YouTube video, summarises it, and saves it to the **Student Notes** database.

**Request body (JSON):**
```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```
**Response:** `{ "success": true, "notion_page_id": "..." }`

---

### `POST /codeforces`
Parses a Codeforces problem page and saves the problem details to the **CP Tracker** database.

**Request body (JSON):**
```json
{
  "url": "https://codeforces.com/problemset/problem/1234/A"
}
```
**Response:** `{ "success": true, "notion_page_id": "..." }`

---

### `GET /query?q=<text>`
Searches the Notion workspace for pages matching the query string.

**Example:** `GET /query?q=dynamic+programming`

**Response:** `{ "results": [ { "title": "...", "url": "..." }, ... ] }`

---

### `GET /calendar`
Returns upcoming exam or event dates from the Notion Calendar database, sorted by date ascending.

**Response:** `{ "events": [ { "name": "...", "date": "YYYY-MM-DD" }, ... ] }`

---

## Notion Databases

### Student Notes DB (`NOTION_NOTES_DB_ID`)

| Property | Type | Description |
|----------|------|-------------|
| `title` | Title | Page/article title |
| `content` | Rich Text | Full extracted text or transcript |
| `tags` | Multi-select | LLM-generated topic tags |
| `source_url` | URL | Original URL of the content |
| `date_saved` | Date | Timestamp when captured |
| `summary` | Rich Text | LLM-generated 2–3 sentence summary |

### CP Tracker DB (`NOTION_CP_DB_ID`)

| Property | Type | Description |
|----------|------|-------------|
| `problem_name` | Title | Name of the Codeforces problem |
| `url` | URL | Direct link to the problem |
| `difficulty` | Select | e.g. 800, 1200, 1600, 2000 |
| `status` | Select | `solved` or `unsolved` |
| `date_attempted` | Date | Date first captured or attempted |
| `notes` | Rich Text | Personal notes or solution approach |

---

## Environment Variables Required

All variables must be present in `.env` (copied from `.env.example`). The app will fail to start if any required variable is missing.

| Variable | Source | Description |
|----------|--------|-------------|
| `OPENROUTER_API_KEY` | [openrouter.ai](https://openrouter.ai) → Keys | API key for LLM calls |
| `NOTION_TOKEN` | Notion → Settings → Integrations | Internal integration secret |
| `NOTION_NOTES_DB_ID` | Notion URL of the Student Notes database | The 32-char database ID |
| `NOTION_CP_DB_ID` | Notion URL of the CP Tracker database | The 32-char database ID |
| `NOTION_CALENDAR_DB_ID` | Notion URL of the Calendar database | The 32-char database ID |
| `FLASK_PORT` | Set manually | Port Flask listens on — default `5000` |
| `FLASK_DEBUG` | Set manually | `True` during development, `False` in production |

---

## Critical Rules for AI Agents

1. **Never hardcode secrets.** All API keys and tokens must be read from `os.environ` or via `python-dotenv`. No exceptions.

2. **Check before installing packages.** Before adding any Python dependency, run `pip show <package>` to confirm it is not already installed. Only install if absent.

3. **CORS must be enabled on all Flask routes.** The Chrome extension origin (`chrome-extension://`) is blocked by browsers unless `flask-cors` is applied globally in `app.py`.

4. **All Notion operations go through `notion_writer.py`.** Never import `notion_client` or call any Notion API directly from `app.py` or any parser.

5. **All LLM calls go through `llm.py`.** Never make `requests` or `httpx` calls to OpenRouter from any file other than `llm.py`.

6. **`popup.js` communicates with the backend only via `fetch()`.** No WebSockets, no direct DOM scraping of external pages from the popup.

7. **`content.js` is read-only with respect to the host page.** It only reads selected text and the page URL — it must never modify the DOM of the host page or make network requests directly.

8. **Do not change the database schema without updating this file.** Any addition or rename of a Notion DB property must be reflected in the "Notion Databases" section above.

9. **Every new API endpoint must be documented here** in the "API Endpoints" section before being considered complete.

---

## How to Run

### Backend

```bash
cd backend
pip install -r ../requirements.txt
python app.py
# Server starts at http://localhost:5000
```

### Chrome Extension

1. Open Chrome and navigate to `chrome://extensions`
2. Enable **Developer mode** (toggle in the top-right corner)
3. Click **Load unpacked**
4. Select the `extension/` folder from this repository
5. The extension icon will appear in the Chrome toolbar

### Environment Setup

```bash
cp .env.example .env
# Fill in all values in .env before starting the backend
```
