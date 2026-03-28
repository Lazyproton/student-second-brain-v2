# Fetches and parses transcripts from YouTube videos using youtube-transcript-api

import re
import requests
from bs4 import BeautifulSoup

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
except ImportError:
    raise ImportError(
        "youtube-transcript-api is not installed. "
        "Run: pip install youtube-transcript-api"
    )


def _extract_video_id(url: str) -> str:
    """Extracts the 11-char video ID from any standard YouTube URL format."""
    patterns = [
        r"(?:v=)([a-zA-Z0-9_-]{11})",
        r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
        r"(?:shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from URL: {url}")


# Accepts a full YouTube video URL, fetches its auto-generated or manual transcript
# via the youtube-transcript-api, joins all caption chunks into one clean string,
# and returns the transcript along with the video ID and word count.
def get_youtube_transcript(video_url: str) -> dict:
    """
    Fetches the full transcript for a YouTube video.

    Args:
        video_url (str): Full YouTube URL, e.g. https://www.youtube.com/watch?v=xxxxx

    Returns:
        dict with keys:
            - "transcript" (str): Full joined transcript text.
            - "video_id"   (str): Extracted video ID.
            - "word_count" (int): Number of words in the transcript.
        On error:
            - "transcript" (str): ""
            - "video_id"   (str): ""
            - "error"      (str): Error message.
    """
    try:
        video_id = _extract_video_id(video_url)
        
        # Scrape the actual video title from the page HTML
        title = f"YouTube Video {video_id}"
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = requests.get(video_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                # First try the <title> tag
                if soup.title and soup.title.string:
                    raw_title = soup.title.string.strip()
                    if raw_title.endswith(" - YouTube"):
                        raw_title = raw_title[:-10]
                    title = raw_title
                # Second try the OpenGraph meta tag if the first was too generic
                if title == f"YouTube Video {video_id}" or title == "YouTube":
                    og_title = soup.find("meta", property="og:title")
                    if og_title and og_title.get("content"):
                        title = og_title["content"].strip()
        except Exception as e:
            print(f"[youtube] Failed to scrape title: {e}")

        api = YouTubeTranscriptApi()
        transcript_list = api.fetch(video_id)

        # Join all caption chunks into one readable string
        transcript = " ".join(entry.text for entry in transcript_list)
        # Collapse any double spaces left by [Music] / [Applause] tags
        transcript = re.sub(r" {2,}", " ", transcript).strip()

        return {
            "transcript": transcript,
            "video_id":   video_id,
            "title":      title,
            "word_count": len(transcript.split()),
        }

    except TranscriptsDisabled:
        return {"transcript": "", "video_id": "", "error": "Transcripts are disabled for this video."}
    except NoTranscriptFound:
        return {"transcript": "", "video_id": "", "error": "No transcript found for this video."}
    except Exception as e:
        return {"transcript": "", "video_id": "", "error": str(e)}
