"""YouTube URL validation and caption retrieval, without video downloads."""

import re
from urllib.parse import parse_qs, urlparse

from pydantic import ValidationError
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound, RequestBlocked, TranscriptsDisabled,
    VideoUnavailable, YouTubeTranscriptApiException,
)

from .errors import LectureSkipperError
from .models import Caption


def parse_video_id(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value
    try:
        parsed = urlparse(value)
        host = parsed.hostname
    except ValueError as error:
        raise LectureSkipperError("Invalid YouTube URL. Paste a full https://www.youtube.com/watch?v=... link.") from error
    if parsed.scheme not in {"http", "https"}:
        raise LectureSkipperError("Enter a YouTube URL or an 11-character video ID.")
    parts = parsed.path.strip("/").split("/")
    video_id = ""
    if host in {"youtu.be", "www.youtu.be"} and len(parts) == 1:
        video_id = parts[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "www.youtube-nocookie.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif len(parts) == 2 and parts[0] in {"embed", "shorts", "live"}:
            video_id = parts[1]
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise LectureSkipperError("The URL does not contain a valid YouTube video ID. Use a video link, not a playlist or channel.")
    return video_id


class _TimeoutSession(requests.Session):
    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", 30)
        return super().request(method, url, **kwargs)


def fetch_transcript(video_id: str, languages=("en",)) -> list[Caption]:
    try:
        with _TimeoutSession() as session:
            transcript = YouTubeTranscriptApi(http_client=session).fetch(video_id, languages=languages)
            captions = [Caption(start=s.start, duration=s.duration, text=s.text) for s in transcript]
    except (NoTranscriptFound, TranscriptsDisabled) as error:
        raise LectureSkipperError("No captions are available in the requested languages. Check YouTube's CC menu, choose another video, or use --languages.") from error
    except RequestBlocked as error:
        raise LectureSkipperError("YouTube blocked transcript retrieval from this connection. Try again later or from another network; no video was downloaded.") from error
    except VideoUnavailable as error:
        raise LectureSkipperError("This video is unavailable. Check that it is public and the URL is correct.") from error
    except (YouTubeTranscriptApiException, requests.RequestException) as error:
        raise LectureSkipperError(f"Could not retrieve captions. Check your internet connection and video accessibility. Details: {error}") from error
    except ValidationError as error:
        raise LectureSkipperError("YouTube returned invalid caption timestamps or text. Try another lecture.") from error
    if not captions or not any(c.text.strip() for c in captions):
        raise LectureSkipperError("The transcript has no usable text. Choose a lecture with accessible captions.")
    return captions
