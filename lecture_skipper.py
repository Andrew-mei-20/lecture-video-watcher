"""Compatibility helpers for the original single-module Python API."""

from ai_lecture_skipper.analyzer import DEFAULT_MODEL
from ai_lecture_skipper.models import Caption, Classification
from ai_lecture_skipper.pipeline import analyze_lecture
from ai_lecture_skipper.segmentation import segment_transcript
from ai_lecture_skipper.youtube import parse_video_id


def chunk_transcript(snippets, seconds=300, max_chars=12000):
    captions = [Caption(start=s.start, duration=s.duration, text=s.text) for s in snippets]
    return [{"start": chunk.start, "end": chunk.end,
             "text": " ".join(caption.text for caption in chunk.captions)}
            for chunk in segment_transcript(captions, seconds, max_chars)]


def validate_classification(data):
    return Classification.model_validate(data).model_dump()


def analyze(video_id, languages, model=DEFAULT_MODEL, chunk_seconds=300, progress=None):
    # Preserve the original full-lecture API and legacy 'url' output key.
    result = analyze_lecture(video_id, languages, model, chunk_seconds,
                             max_minutes=None, progress=progress)
    return {"video_id": result.video_id,
            "segments": [{**segment.model_dump(), "url": segment.youtube_url}
                         for segment in result.segments]}
