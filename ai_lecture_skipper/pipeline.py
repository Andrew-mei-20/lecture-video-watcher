"""Coordinate retrieval, segmentation, and local analysis."""

from .analyzer import DEFAULT_MODEL, LocalAnalyzer
from .models import AnalysisResult
from .segmentation import limit_transcript, segment_transcript
from .youtube import fetch_transcript, parse_video_id


def analyze_lecture(url, languages=("en",), model=DEFAULT_MODEL, chunk_seconds=300,
                    max_minutes=15, timeout=600, progress=None):
    def report(message):
        if progress:
            progress(message)

    video_id = parse_video_id(url)
    analyzer = LocalAnalyzer(model=model, timeout=timeout)
    report("Checking local Ollama server and model...")
    analyzer.check_ready()
    report("Retrieving timestamped captions...")
    captions = fetch_transcript(video_id, languages)
    selected, truncated = limit_transcript(captions, max_minutes)
    chunks = segment_transcript(selected, seconds=chunk_seconds)
    report(f"Prepared {len(chunks)} sections; inference runs one section at a time.")
    segments = []
    for index, chunk in enumerate(chunks, 1):
        report(f"Analyzing section {index}/{len(chunks)} ({chunk.start:g}-{chunk.end:g}s)...")
        segments.append(analyzer.analyze_chunk(chunk, video_id))
    return AnalysisResult(video_id=video_id, model=model, max_minutes=max_minutes,
                          truncated=truncated, segments=segments)
