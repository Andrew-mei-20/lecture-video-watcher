"""Lossless caption grouping with duration and context bounds."""

import math

from .errors import LectureSkipperError
from .models import Caption, TranscriptChunk

DEFAULT_MAX_CHARS = 3000


def segment_transcript(captions: list[Caption], seconds=300, max_chars=DEFAULT_MAX_CHARS):
    """Retain every source caption; reject oversize captions rather than truncate.

    The text limit applies to UTF-8 bytes too, providing a conservative context
    bound for non-ASCII captions. Small captions may therefore form sections
    shorter than the target duration.
    """
    if not math.isfinite(seconds) or seconds <= 0 or max_chars <= 0:
        raise LectureSkipperError("Chunk limits must be positive and finite.")
    if not captions or not any(c.text.strip() for c in captions):
        raise LectureSkipperError("The transcript has no usable captions.")
    chunks = []
    current = []
    size = 0
    previous_start = -1
    for caption in captions:
        if caption.start < previous_start:
            raise LectureSkipperError("Transcript timestamps are out of order; analysis stopped to preserve accurate links.")
        previous_start = caption.start
        caption_size = len(caption.text.encode("utf-8"))
        if caption_size > max_chars:
            raise LectureSkipperError(f"A caption at {caption.start:g}s exceeds the {max_chars}-byte context limit. No text was silently removed.")
        if current and (caption.end - current[0].start > seconds or size + 1 + caption_size > max_chars):
            chunks.append(TranscriptChunk(captions=current))
            current = []
            size = 0
        size += caption_size + (1 if current else 0)
        current.append(caption)
    if current:
        chunks.append(TranscriptChunk(captions=current))
    return chunks


def limit_transcript(captions: list[Caption], max_minutes: float | None):
    if max_minutes is None:
        return captions, False
    if not math.isfinite(max_minutes) or max_minutes <= 0:
        raise LectureSkipperError("Maximum minutes must be positive and finite, or use --full.")
    # Keep a complete caption crossing the cutoff instead of cutting its text.
    included = [caption for caption in captions if caption.start < max_minutes * 60]
    return included, len(included) < len(captions)
