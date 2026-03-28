# Scrapes Codeforces problem pages using requests and BeautifulSoup4

import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# Accepts a Codeforces problem URL, fetches the HTML page, and uses BeautifulSoup
# to extract the problem name, statement, time/memory limits, and input/output
# format as plain text with all HTML tags stripped.
def get_cf_problem(problem_url: str) -> dict:
    """
    Scrapes a Codeforces problem page and returns structured problem data.

    Args:
        problem_url (str): e.g. https://codeforces.com/problemset/problem/1/A

    Returns:
        dict with keys:
            - "problem_name"  (str): Problem title.
            - "statement"     (str): Full problem statement as plain text.
            - "time_limit"    (str): e.g. "2 seconds".
            - "memory_limit"  (str): e.g. "256 megabytes".
            - "url"           (str): The original URL passed in.
        On error:
            - "problem_name"  (str): ""
            - "statement"     (str): ""
            - "error"         (str): Error message.
    """
    try:
        if "codeforces.com" not in problem_url:
            raise ValueError(f"Not a Codeforces URL: {problem_url}")

        response = requests.get(problem_url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # ── Problem name ────────────────────────────────────────────────────
        name_tag = soup.select_one(".problem-statement .title")
        problem_name = name_tag.get_text(strip=True) if name_tag else "Unknown Problem"

        # ── Time limit ──────────────────────────────────────────────────────
        time_tag = soup.select_one(".time-limit")
        time_limit = _strip_label(time_tag)

        # ── Memory limit ────────────────────────────────────────────────────
        memory_tag = soup.select_one(".memory-limit")
        memory_limit = _strip_label(memory_tag)

        # ── Problem statement (body text only) ──────────────────────────────
        statement_div = soup.select_one(".problem-statement")
        if statement_div:
            # Remove the header block (title + limits) so only body text remains
            for header in statement_div.select(".header"):
                header.decompose()
            statement = statement_div.get_text(separator="\n", strip=True)
            # Collapse excessive blank lines
            statement = re.sub(r"\n{3,}", "\n\n", statement).strip()
        else:
            statement = ""

        return {
            "problem_name": problem_name,
            "statement":    statement,
            "time_limit":   time_limit,
            "memory_limit": memory_limit,
            "url":          problem_url,
        }

    except requests.exceptions.Timeout:
        return {"problem_name": "", "statement": "", "error": "Request timed out fetching the problem page."}
    except requests.exceptions.HTTPError as e:
        return {"problem_name": "", "statement": "", "error": f"HTTP error: {e}"}
    except Exception as e:
        return {"problem_name": "", "statement": "", "error": str(e)}


def _strip_label(tag) -> str:
    """Removes the Notion property-title label inside a limit tag and returns the value."""
    if not tag:
        return ""
    label = tag.select_one(".property-title")
    if label:
        label.decompose()
    return tag.get_text(strip=True)
