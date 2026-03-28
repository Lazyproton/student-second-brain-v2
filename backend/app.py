# Flask application entry point — defines all API routes and wires together parsers, llm.py, and notion_writer.py

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables from .env at startup
load_dotenv()

# Internal modules — all Notion and LLM calls go through these exclusively
import llm
from notion_writer import (
    save_to_notes_db,
    save_to_cp_tracker,
    search_notes,
    get_upcoming_exams,
    get_all_subjects,
    create_subject_database,
    save_to_subject_db,
    get_subject_notes,
)
import notion_writer
from parsers import parse_youtube, parse_codeforces
from google_calendar import sync_exam_to_google_calendar

app = Flask(__name__)
# Enable CORS on all routes so the Chrome extension can reach the backend
CORS(app, origins=["chrome-extension://*", "http://localhost:*"])


# ──────────────────────────────────────────────
# POST /capture
# Saves a webpage URL or selected text to the Student Notes DB
# ──────────────────────────────────────────────
@app.route("/capture", methods=["POST"])
def capture():
    try:
        data = request.get_json(force=True)
        content      = data.get("content", "")
        url          = data.get("url", "")
        title        = data.get("title", "Untitled")
        subject_name = data.get("subject_name", "").strip()

        if not content and not url:
            print("[/capture] Error: Either content or url is required.")
            return jsonify({"success": False, "error": "Either 'content' or 'url' is required."}), 400

        # Fallback empty content to title
        content = content or title
        print(f"[/capture] Received request: title='{title}', url='{url}', subject='{subject_name}', content_length={len(content)}")

        # Use LLM to generate summary and tags
        analysis = llm.summarize_content(content or url, "webpage")
        summary = analysis.get("summary", "")
        tags    = analysis.get("tags", [])

        if subject_name:
            # Route to the per-subject database when a subject is specified
            notion_page_id = save_to_subject_db(
                subject_name=subject_name,
                title=title,
                content=content,
                summary=summary,
                tags=tags,
                source_url=url,
            )
        else:
            notion_page_id = save_to_notes_db(
                title=title,
                content=content,
                summary=summary,
                tags=tags,
                source_url=url,
            )

        if not notion_page_id:
            print(f"[/capture] Failed to create Notion page for '{title}'")
            return jsonify({"success": False, "error": "Failed to create Notion page. Check API token/database permissions."}), 500

        print(f"[/capture] Success! Notion page ID: {notion_page_id}")
        return jsonify({"success": True, "notion_page_id": notion_page_id})

    except Exception as e:
        print(f"[/capture] Exception: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ──────────────────────────────────────────────
# POST /youtube
# Fetches a YouTube transcript, summarises it, and saves to Student Notes DB
# ──────────────────────────────────────────────
@app.route("/youtube", methods=["POST"])
def youtube():
    try:
        data = request.get_json(force=True)
        video_url = data.get("video_url", "")

        if not video_url:
            return jsonify({"success": False, "error": "'video_url' is required."}), 400

        result = parse_youtube.get_youtube_transcript(video_url)
        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400
            
        transcript = result["transcript"]
        title = result.get("title", f"YouTube: {video_url}")
        
        print(f"[youtube] Fetched transcript for video: '{title}'")
        
        # Pass title context to LLM so the summary can mention the video title naturally
        context_text = f"Title: {title}\n\n{transcript}"
        analysis = llm.summarize_content(context_text, "youtube")
        
        summary = analysis.get("summary", "")
        tags = analysis.get("tags", [])

        notion_page_id = notion_writer.save_to_notes_db(
            title=title,
            content=transcript,
            summary=summary,
            tags=tags,
            source_url=video_url,
        )

        if not notion_page_id:
            return jsonify({"success": False, "error": "Failed to create Notion page. Check API token/database permissions."}), 500

        return jsonify({"success": True, "notion_page_id": notion_page_id})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ──────────────────────────────────────────────
# POST /codeforces
# Parses a Codeforces problem and saves to CP Tracker DB
# ──────────────────────────────────────────────
@app.route("/codeforces", methods=["POST"])
def codeforces():
    try:
        data = request.get_json(force=True)
        problem_url = data.get("problem_url", "")
        problem_name = data.get("problem_name", "Unknown CF Problem")
        status = data.get("status", "unsolved")
        notes = data.get("notes", "")

        if not problem_url:
            return jsonify({"success": False, "error": "'problem_url' is required."}), 400

        if status not in ("solved", "unsolved"):
            return jsonify({"success": False, "error": "'status' must be 'solved' or 'unsolved'."}), 400

        # Summarize the raw problem statement into the notes section
        summary_text = ""
        if notes:
            analysis = llm.summarize_content(notes, "codeforces")
            summary_text = analysis.get("summary", "")

        # Codeforces blocks requests with 403 Forbidden now. 
        # Bypass scraping and just use the URL and Tab Title directly.
        notion_page_id = notion_writer.save_to_cp_tracker(
            problem_name=problem_name,
            url=problem_url,
            difficulty="",  # The parser doesn't extract difficulty currently
            status=status,
            notes=summary_text,
        )

        if not notion_page_id:
            return jsonify({"success": False, "error": "Failed to create Notion page. Check API token/database permissions."}), 500

        return jsonify({"success": True, "notion_page_id": notion_page_id})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ──────────────────────────────────────────────
# GET /query?q=<search_text>
# Searches the Notion workspace and returns matching pages
# ──────────────────────────────────────────────
@app.route("/query", methods=["GET"])
def query():
    try:
        q = request.args.get("q", "").strip()

        if not q:
            return jsonify({"success": False, "error": "Query parameter 'q' is required."}), 400

        results = notion_writer.search_notes(q)
        return jsonify({"results": results})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ──────────────────────────────────────────────
# GET /calendar
# Returns upcoming exam dates from Notion Calendar and syncs to Google Calendar
# ──────────────────────────────────────────────
@app.route("/calendar", methods=["GET"])
def calendar():
    try:
        exams = notion_writer.get_upcoming_exams()

        # Sync each exam to Google Calendar (best-effort — don't fail the response on error)
        for exam in (exams or []):
            try:
                sync_exam_to_google_calendar(exam.get("exam_name"), exam.get("date"))
            except Exception as sync_err:
                print(f"[calendar] Google Calendar sync failed for '{exam.get('exam_name')}': {sync_err}")

        return jsonify({"exams": exams})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ──────────────────────────────────────────────
# GET /subjects
# Lists all subjects registered in the Master Index database
# ──────────────────────────────────────────────
@app.route("/subjects", methods=["GET"])
def subjects_list():
    try:
        subjects = get_all_subjects()
        return jsonify({"success": True, "subjects": subjects})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ──────────────────────────────────────────────
# POST /subjects/create
# Creates a new subject-specific Notion database and registers it
# ──────────────────────────────────────────────
@app.route("/subjects/create", methods=["POST"])
def subjects_create():
    try:
        data         = request.get_json(force=True)
        subject_name = data.get("subject_name", "").strip()

        if not subject_name:
            return jsonify({"success": False, "error": "'subject_name' is required."}), 400

        database_id = create_subject_database(subject_name)

        if not database_id:
            return jsonify({"success": False, "error": f"Failed to create database for '{subject_name}'."}), 500

        return jsonify({"success": True, "subject_name": subject_name, "database_id": database_id})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ──────────────────────────────────────────────
# POST /capture/subject
# Captures a note directly into a subject-specific Notion database
# ──────────────────────────────────────────────
@app.route("/capture/subject", methods=["POST"])
def capture_subject():
    try:
        data         = request.get_json(force=True)
        subject_name = data.get("subject_name", "").strip()
        content      = data.get("content", "")
        url          = data.get("url", "")
        title        = data.get("title", "Untitled")

        if not subject_name:
            print("[/capture/subject] Error: subject_name is required.")
            return jsonify({"success": False, "error": "'subject_name' is required."}), 400

        if not content and not url:
            print("[/capture/subject] Error: Either content or url is required.")
            return jsonify({"success": False, "error": "Either 'content' or 'url' is required."}), 400

        # Fallback empty content to title
        content = content or title
        print(f"[/capture/subject] Received request: subject='{subject_name}', title='{title}', url='{url}', content_length={len(content)}")

        # Generate summary and tags via LLM
        analysis = llm.summarize_content(content or url, "webpage")
        summary  = analysis.get("summary", "")
        tags     = analysis.get("tags", [])

        notion_page_id = save_to_subject_db(
            subject_name=subject_name,
            title=title,
            content=content,
            summary=summary,
            tags=tags,
            source_url=url,
        )

        if not notion_page_id:
            print(f"[/capture/subject] Failed to create Notion page in subject '{subject_name}'.")
            return jsonify({"success": False, "error": "Failed to create Notion page."}), 500

        print(f"[/capture/subject] Success! Notion page ID: {notion_page_id}")
        return jsonify({"success": True, "notion_page_id": notion_page_id, "subject_name": subject_name})

    except Exception as e:
        print(f"[/capture/subject] Exception: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ──────────────────────────────────────────────
# GET /test-capture
# Test endpoint to verify Notion connection
# ──────────────────────────────────────────────
@app.route("/test-capture", methods=["GET"])
def test_capture():
    try:
        print("[/test-capture] Running test capture...")
        notion_page_id = save_to_notes_db(
            title="Test Note",
            content="This is a test",
            summary="Test summary",
            tags=["test"],
            source_url="http://test.com",
        )
        if not notion_page_id:
            print("[/test-capture] Failed to create test page.")
            return jsonify({"success": False, "error": "Failed to create test page"}), 500
            
        print(f"[/test-capture] Success! Page ID: {notion_page_id}")
        return jsonify({"success": True, "page_id": notion_page_id})
    except Exception as e:
        print(f"[/test-capture] Exception: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("FLASK_PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "True").lower() == "true"
    print(f"Starting Student Second Brain backend on port {port} (debug={debug})")
    app.run(host="0.0.0.0", port=port, debug=debug)
