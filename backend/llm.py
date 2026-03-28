# Handles all LLM calls via the OpenRouter API — no other file should call OpenRouter directly

import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Model is configurable via .env — defaults to Gemini 2.0 Flash if not set
MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")


def _call_llm(prompt: str) -> str:
    """Core helper — sends a prompt to OpenRouter and returns the raw response text."""
    if not OPENROUTER_API_KEY:
        raise EnvironmentError("OPENROUTER_API_KEY is not set. Check your .env file.")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://student-second-brain.local",
        "X-Title": "Student Second Brain V2",
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }

    response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


# ──────────────────────────────────────────────────────────────────────────────
# Analyses captured content and returns a structured dict with a summary,
# topic tags, and a short main-topic label. content_type helps tailor the
# prompt to the kind of material being summarised (webpage, youtube, pdf,
# codeforces).
# ──────────────────────────────────────────────────────────────────────────────
def summarize_content(content: str, content_type: str) -> dict:
    """
    Sends content to the LLM and returns a structured summary dict.

    Args:
        content (str): The raw text to summarise (will be trimmed to 8000 chars).
        content_type (str): One of "webpage", "youtube", "pdf", "codeforces".

    Returns:
        dict with keys:
            - "summary" (str): 3-sentence summary.
            - "tags" (list[str]): 3–5 relevant topic tags.
            - "topic" (str): Main topic in 5 words or less.
        On any failure, returns {"summary": "", "tags": [], "topic": ""}.
    """
    trimmed = content[:8000]

    if content_type == "codeforces":
        prompt = f"""You are analyzing a competitive programming problem. 
Your job is to extract and summarize ONLY the problem statement.

Rules:
- Describe what the problem is asking in 2-3 simple sentences
- Mention the input format briefly
- Mention the output format briefly
- Mention any important constraints (array size, time limit etc.)
- Do NOT give any hints toward the solution
- Do NOT mention algorithms, data structures, or approaches to solve it
- Do NOT say things like 'use dynamic programming' or 'this can be solved by'
- Generate 3-5 tags that describe the problem topic (example: arrays, strings, graphs)
- Identify the difficulty topic in 5 words or less

Return your response in exactly this format:
SUMMARY: <2-3 sentence problem description>
TAGS: <tag1>, <tag2>, <tag3>
TOPIC: <5 words or less>

Content:
{trimmed}"""
    else:
        type_context = {
            "webpage":    "a webpage article",
            "youtube":    "a YouTube video transcript",
            "pdf":        "a PDF document",
        }.get(content_type, "a piece of content")

        prompt = f"""You are a helpful study assistant analysing {type_context}.

Given the following content, respond with EXACTLY this format and nothing else:

SUMMARY: <3-sentence summary suitable for student notes>
TAGS: <3 to 5 relevant tags, comma-separated, all lowercase>
TOPIC: <the main topic in 5 words or less>

Content:
{trimmed}"""

    try:
        raw = _call_llm(prompt)
        result = {"summary": "", "tags": [], "topic": ""}

        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("SUMMARY:"):
                result["summary"] = line[len("SUMMARY:"):].strip()
            elif line.startswith("TAGS:"):
                tags_raw = line[len("TAGS:"):].strip()
                result["tags"] = [t.strip().lower() for t in tags_raw.split(",") if t.strip()][:5]
            elif line.startswith("TOPIC:"):
                result["topic"] = line[len("TOPIC:"):].strip()

        return result

    except Exception as e:
        print(f"[llm] summarize_content failed: {e}")
        return {"summary": "", "tags": [], "topic": ""}


# ──────────────────────────────────────────────────────────────────────────────
# Takes a natural language search query from the user (e.g. "show me graph
# problems I solved") and asks the LLM to distil it into a clean, concise
# search string suitable for passing directly to the Notion search API.
# ──────────────────────────────────────────────────────────────────────────────
def search_query_to_notion_filter(query: str) -> str:
    """
    Converts a natural language query into a clean Notion search string.

    Args:
        query (str): Natural language input, e.g. "show me graph problems".

    Returns:
        str: A concise keyword string for Notion search, e.g. "graph problems".
             Falls back to the original query on failure.
    """
    prompt = (
        "You are a search assistant. "
        "Extract the key search terms from the following natural language query "
        "so they can be used in a Notion database search. "
        "Return ONLY the search terms — no explanation, no punctuation, just the keywords.\n\n"
        f"Query: {query}"
    )

    try:
        return _call_llm(prompt).strip()
    except Exception as e:
        print(f"[llm] search_query_to_notion_filter failed: {e}")
        return query  # Fall back to the raw query so search still works
