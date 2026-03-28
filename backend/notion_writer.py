# Handles all Notion read and write operations — no other file should call Notion directly

import os
from datetime import datetime, timezone
from typing import Optional
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

# ── Notion client ──────────────────────────────────────────────────────────────
_token = os.environ.get("NOTION_TOKEN")
if not _token:
    raise EnvironmentError("NOTION_TOKEN is not set. Check your .env file.")

notion = Client(auth=_token)

# ── Database IDs ───────────────────────────────────────────────────────────────
NOTES_DB_ID        = os.environ.get("NOTION_NOTES_DB_ID")
CP_DB_ID           = os.environ.get("NOTION_CP_DB_ID")
CALENDAR_DB_ID     = os.environ.get("NOTION_CALENDAR_DB_ID")
MASTER_INDEX_DB_ID = os.environ.get("NOTION_MASTER_INDEX_DB_ID")
PARENT_PAGE_ID     = os.environ.get("NOTION_PARENT_PAGE_ID")


# ── Internal helpers ───────────────────────────────────────────────────────────

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def _rich_text(value: str) -> list:
    """Wraps a string in Notion rich_text format, capped at 2000 chars."""
    return [{"type": "text", "text": {"content": str(value)[:2000]}}]

def _multi_select(tags: list) -> list:
    """Converts a list of strings to Notion multi_select format."""
    return [{"name": str(t)[:100]} for t in (tags or [])]

def _page_title(page: dict) -> str:
    """Extracts plain-text title from a Notion page object."""
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            parts = prop.get("title", [])
            return "".join(p.get("plain_text", "") for p in parts)
    return "Untitled"

def _page_rich_text(page: dict, key: str) -> str:
    """Extracts plain text from a rich_text property."""
    prop = page.get("properties", {}).get(key, {})
    parts = prop.get("rich_text", [])
    return "".join(p.get("plain_text", "") for p in parts)

def _page_multi_select(page: dict, key: str) -> list:
    """Extracts multi_select values as a list of name strings."""
    prop = page.get("properties", {}).get(key, {})
    return [opt.get("name", "") for opt in prop.get("multi_select", [])]

def _page_url(page: dict, key: str) -> str:
    prop = page.get("properties", {}).get(key, {})
    return prop.get("url") or ""

def _text_to_blocks(text: str) -> list:
    """Converts multiline string into a list of Notion paragraph blocks."""
    if not text:
        return []
    # Split by double newline or larger to separate paragraphs
    paragraphs = text.split("\n\n")
    blocks = []
    for p in paragraphs[:50]: # Limit to 50 blocks to avoid rate limits/timeouts
        if not p.strip():
            continue
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": p[:2000]}}]
            }
        })
    return blocks

# ── 1. save_to_notes_db ────────────────────────────────────────────────────────
# Creates a new page in the Student Notes database with a title, full content,
# LLM summary, topic tags, source URL, and today's date.
def save_to_notes_db(
    title: str,
    content: str,
    summary: str,
    tags: list,
    source_url: str,
) -> Optional[str]:
    """
    Saves a captured note to the Student Notes Notion database.

    Returns:
        str: The new Notion page ID, or None on failure.
    """
    try:
        if not NOTES_DB_ID:
            raise EnvironmentError("NOTION_NOTES_DB_ID is not set.")

        # Map properties to exact Notion DB property names (case-sensitive)
        properties = {
            "Title":      {"title":      _rich_text(title or "Untitled")},
            "Summary":    {"rich_text":  _rich_text(summary or "")},
            "Tags":       {"multi_select": _multi_select(tags)},
            "Subject":    {"select":     {"name": "General"}}, # Default select option
        }
        if source_url:
            properties["Source URL"] = {"url": source_url}

        # Long content goes into the page body (children) as blocks
        children = _text_to_blocks(content)

        print(f"[notion_writer] Creating page in Notes DB '{NOTES_DB_ID}' for title: '{title}'...")
        page = notion.pages.create(
            parent={"database_id": NOTES_DB_ID},
            properties=properties,
            children=children[:100], # Notion limit is 100 on create
        )
        print(f"[notion_writer] Page created successfully! ID: {page['id']}")
        return page["id"]

    except Exception as e:
        print(f"[notion_writer] save_to_notes_db error: {e}")
        return None


# ── 2. save_to_cp_tracker ─────────────────────────────────────────────────────
# Creates a new page in the CP Tracker database with problem metadata,
# difficulty, solve status, personal notes, and today's date.
def save_to_cp_tracker(
    problem_name: str,
    url: str,
    difficulty: str,
    status: str,
    notes: str = "",
) -> Optional[str]:
    """
    Saves a Codeforces problem to the CP Tracker Notion database.

    Args:
        difficulty (str): "Easy", "Medium", or "Hard".
        status (str): "solved" or "unsolved".

    Returns:
        str: The new Notion page ID, or None on failure.
    """
    try:
        if not CP_DB_ID:
            raise EnvironmentError("NOTION_CP_DB_ID is not set.")

        # Map properties to exact Notion DB property names (case-sensitive)
        properties = {
            "Title":      {"title":     _rich_text(problem_name or "Unknown Problem")},
            "Status":     {"select":    {"name": status.capitalize()}}, # Solved/Unsolved
        }
        if url:
            properties["URL"] = {"url": url}
        if difficulty:
            properties["Difficulty"] = {"select": {"name": difficulty}}
        if notes:
            properties["Notes"] = {"rich_text": _rich_text(notes)}

        page = notion.pages.create(
            parent={"database_id": CP_DB_ID},
            properties=properties,
        )
        return page["id"]

    except Exception as e:
        print(f"[notion_writer] save_to_cp_tracker error: {e}")
        return None


# ── 3. search_notes ───────────────────────────────────────────────────────────
# Searches the entire Notion workspace using the provided query string and
# returns up to 10 matching pages with their title, URL, and summary.
def search_notes(query: str) -> Optional[list]:
    """
    Full-text search across the Notion workspace.

    Returns:
        list[dict]: Up to 10 results with "title", "url", "summary" keys.
                    Returns None on failure.
    """
    try:
        response = notion.search(
            query=query,
            filter={"property": "object", "value": "page"},
            sort={"direction": "descending", "timestamp": "last_edited_time"},
            page_size=10,
        )

        results = []
        for page in response.get("results", []):
            results.append({
                "title":   _page_title(page),
                "url":     page.get("url", ""),
                "summary": _page_rich_text(page, "summary"),
            })
        return results

    except Exception as e:
        print(f"[notion_writer] search_notes error: {e}")
        return None


# ── 4. get_upcoming_exams ─────────────────────────────────────────────────────
# Queries the Exam Calendar database for events on or after today, sorted by
# date ascending. Returns each event's name, date, and subject.
def get_upcoming_exams():
    try:
        notion_calendar_db_id = os.environ.get("NOTION_CALENDAR_DB_ID")
        if not notion_calendar_db_id:
            print("[notion_writer] NOTION_CALENDAR_DB_ID is not set.")
            return []
        
        response = notion.databases.query(
            database_id=notion_calendar_db_id,
            filter={
                "property": "Date",
                "date": {
                    "on_or_after": datetime.today().strftime("%Y-%m-%d")
                }
            },
            sorts=[
                {
                    "property": "Date",
                    "direction": "ascending"
                }
            ]
        )
        
        results = response.get("results", [])
        
        exams = []
        for page in results:
            try:
                props = page["properties"]
                
                exam_name = ""
                if props.get("Name") and props["Name"]["title"]:
                    exam_name = props["Name"]["title"][0]["text"]["content"]
                
                date = ""
                if props.get("Date") and props["Date"]["date"]:
                    date = props["Date"]["date"]["start"]
                
                subject = ""
                if props.get("Subject") and props["Subject"]["rich_text"]:
                    subject = props["Subject"]["rich_text"][0]["text"]["content"]
                
                notes = ""
                if props.get("Notes") and props["Notes"]["rich_text"]:
                    notes = props["Notes"]["rich_text"][0]["text"]["content"]
                
                exams.append({
                    "exam_name": exam_name,
                    "date": date,
                    "subject": subject,
                    "notes": notes
                })
            except Exception as e:
                print(f"[notion_writer] Error parsing exam row: {e}")
                continue
        
        return exams
    
    except Exception as e:
        print(f"[notion_writer] get_upcoming_exams error: {e}")
        return []


# ── 5. get_all_notes ──────────────────────────────────────────────────────────
# Returns the 20 most recently saved pages from the Student Notes database,
# sorted by date_saved descending, with title, summary, tags, and source URL.
def get_all_notes() -> Optional[list]:
    """
    Fetches the last 20 notes from the Student Notes database.

    Returns:
        list[dict]: Each dict has "title", "summary", "tags", "source_url" keys.
                    Returns None on failure.
    """
    try:
        if not NOTES_DB_ID:
            raise EnvironmentError("NOTION_NOTES_DB_ID is not set.")

        response = notion.databases.query(
            database_id=NOTES_DB_ID,
            sorts=[{"property": "date_saved", "direction": "descending"}],
            page_size=20,
        )

        notes = []
        for page in response.get("results", []):
            notes.append({
                "title":      _page_title(page),
                "summary":    _page_rich_text(page, "summary"),
                "tags":       _page_multi_select(page, "tags"),
                "source_url": _page_url(page, "source_url"),
            })
        return notes

    except Exception as e:
        print(f"[notion_writer] get_all_notes error: {e}")
        return None


# ── 6. get_all_subjects ───────────────────────────────────────────────────────
# Queries the Master Index database to retrieve every registered subject and
# its corresponding Notion database ID. Returns an empty list if the Master
# Index DB ID is not configured or if the query fails.
def get_all_subjects() -> list:
    """
    Fetches all subject entries from the Master Index database.

    Returns:
        list[dict]: Each dict has "subject_name" and "database_id" keys.
                    Returns [] on error or if env var is not set.
    """
    try:
        master_index_db_id = os.environ.get("NOTION_MASTER_INDEX_DB_ID")
        if not master_index_db_id:
            print("[notion_writer] NOTION_MASTER_INDEX_DB_ID is not set.")
            return []

        response = notion.databases.query(
            database_id=master_index_db_id,
            page_size=100,
        )

        subjects = []
        for page in response.get("results", []):
            try:
                props = page["properties"]

                # "Subject Name" is the title property
                subject_name = ""
                title_parts = props.get("Subject Name", {}).get("title", [])
                if title_parts:
                    subject_name = title_parts[0]["text"]["content"]

                # "Database ID" is a rich_text property
                database_id = ""
                rt_parts = props.get("Database ID", {}).get("rich_text", [])
                if rt_parts:
                    database_id = rt_parts[0]["text"]["content"]

                if subject_name and database_id:
                    subjects.append({
                        "subject_name": subject_name,
                        "database_id":  database_id,
                    })
            except Exception as row_err:
                print(f"[notion_writer] Error parsing subject row: {row_err}")
                continue

        return subjects

    except Exception as e:
        print(f"[notion_writer] get_all_subjects error: {e}")
        return []


# ── 7. create_subject_database ────────────────────────────────────────────────
# Creates a brand-new Notion database as a child of PARENT_PAGE_ID, pre-wired
# with the standard subject-notes schema. After creation it registers the new
# database in the Master Index so future calls can find it by subject name.
def create_subject_database(subject_name: str) -> Optional[str]:
    """
    Creates a new Notion database for the given subject and registers it in
    the Master Index.

    Args:
        subject_name (str): Human-readable subject, e.g. "Mathematics".

    Returns:
        str: The new database ID, or None on failure.
    """
    try:
        parent_page_id     = os.environ.get("NOTION_PARENT_PAGE_ID")
        master_index_db_id = os.environ.get("NOTION_MASTER_INDEX_DB_ID")

        if not parent_page_id:
            print("[notion_writer] NOTION_PARENT_PAGE_ID is not set.")
            return None
        if not master_index_db_id:
            print("[notion_writer] NOTION_MASTER_INDEX_DB_ID is not set.")
            return None

        # -- Create the subject database ------------------------------------------
        new_db = notion.databases.create(
            parent={"type": "page_id", "page_id": parent_page_id},
            title=[{"type": "text", "text": {"content": f"{subject_name} Notes"}}],
            properties={
                "Name":       {"title": {}},
                "Content":    {"rich_text": {}},
                "Summary":    {"rich_text": {}},
                "Tags":       {"multi_select": {}},
                "Source URL": {"url": {}},
                "Date Saved": {"date": {}},
            },
        )
        new_db_id = new_db["id"]
        print(f"[notion_writer] Created subject DB '{subject_name}': {new_db_id}")

        # -- Register in Master Index ---------------------------------------------
        notion.pages.create(
            parent={"database_id": master_index_db_id},
            properties={
                "Subject Name": {"title":     _rich_text(subject_name)},
                "Database ID":  {"rich_text": _rich_text(new_db_id)},
                "Created At":   {"date":      {"start": _today()}},
            },
        )
        print(f"[notion_writer] Registered '{subject_name}' in Master Index.")

        return new_db_id

    except Exception as e:
        print(f"[notion_writer] create_subject_database error: {e}")
        return None


# ── 8. save_to_subject_db ─────────────────────────────────────────────────────
# Saves a note page to the correct subject-specific database. If the subject
# database does not exist yet, it is created automatically first.
def save_to_subject_db(
    subject_name: str,
    title: str,
    content: str,
    summary: str,
    tags: list,
    source_url: str,
) -> Optional[str]:
    """
    Saves a note to the subject-specific Notion database, auto-creating the
    database if it doesn't exist.

    Returns:
        str: The created page ID, or None on failure.
    """
    try:
        # -- Find or create the subject database ----------------------------------
        subjects = get_all_subjects()
        db_id = next(
            (s["database_id"] for s in subjects
             if s["subject_name"].strip().lower() == subject_name.strip().lower()),
            None,
        )

        if not db_id:
            print(f"[notion_writer] Subject '{subject_name}' not found — creating DB.")
            db_id = create_subject_database(subject_name)
            if not db_id:
                print(f"[notion_writer] Could not create DB for '{subject_name}'.")
                return None

        # -- Save the note page ---------------------------------------------------
        properties: dict = {
            "Name":       {"title":     _rich_text(title or "Untitled")},
            "Summary":    {"rich_text": _rich_text(summary or "")},
            "Tags":       {"multi_select": _multi_select(tags)},
            "Date Saved": {"date":      {"start": _today()}},
        }
        if source_url:
            properties["Source URL"] = {"url": source_url}

        # Long content goes into page body (children), not a property
        children = _text_to_blocks(content)
        if content and not children:
            # Fallback: try storing truncated content in rich_text
            properties["Content"] = {"rich_text": _rich_text(content)}

        print(f"[notion_writer] Creating page in Subject DB '{db_id}' for title: '{title}'...")
        page = notion.pages.create(
            parent={"database_id": db_id},
            properties=properties,
            children=children[:100],  # Notion limit on create
        )
        print(f"[notion_writer] Page created successfully! ID: {page['id']}")
        return page["id"]

    except Exception as e:
        print(f"[notion_writer] save_to_subject_db error: {e}")
        return None


# ── 9. get_subject_notes ─────────────────────────────────────────────────────
# Finds a subject's database by name and returns its 20 most recent notes
# (sorted by Date Saved descending). Returns [] if the subject is unknown
# or if the database query fails.
def get_subject_notes(subject_name: str) -> list:
    """
    Returns the last 20 notes from a subject-specific database.

    Returns:
        list[dict]: Each dict has "title", "summary", "source_url",
                    "date_saved" keys. Returns [] on error.
    """
    try:
        subjects = get_all_subjects()
        db_id = next(
            (s["database_id"] for s in subjects
             if s["subject_name"].strip().lower() == subject_name.strip().lower()),
            None,
        )

        if not db_id:
            print(f"[notion_writer] Subject '{subject_name}' not found in Master Index.")
            return []

        response = notion.databases.query(
            database_id=db_id,
            sorts=[{"property": "Date Saved", "direction": "descending"}],
            page_size=20,
        )

        notes = []
        for page in response.get("results", []):
            try:
                props = page["properties"]

                # Title from "Name" (title property)
                title = ""
                title_parts = props.get("Name", {}).get("title", [])
                if title_parts:
                    title = title_parts[0].get("plain_text", "")

                summary  = _page_rich_text(page, "Summary")
                src_url  = _page_url(page, "Source URL")

                # Date from "Date Saved" date property
                date_saved = ""
                date_prop = props.get("Date Saved", {}).get("date")
                if date_prop:
                    date_saved = date_prop.get("start", "")

                notes.append({
                    "title":      title,
                    "summary":    summary,
                    "source_url": src_url,
                    "date_saved": date_saved,
                })
            except Exception as row_err:
                print(f"[notion_writer] Error parsing subject note row: {row_err}")
                continue

        return notes

    except Exception as e:
        print(f"[notion_writer] get_subject_notes error: {e}")
        return []
