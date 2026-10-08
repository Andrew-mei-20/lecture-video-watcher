"""Validated source captions and model/output schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VISUAL_WARNING = (
    "Transcript-only analysis can miss equations, slides, and other visual content. "
    "Check the video before skipping important material."
)


class Caption(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    start: float = Field(ge=0)
    duration: float = Field(ge=0)
    text: str

    @property
    def end(self) -> float:
        return self.start + self.duration


class TranscriptChunk(BaseModel):
    captions: list[Caption] = Field(min_length=1)

    @property
    def start(self) -> float:
        return self.captions[0].start

    @property
    def end(self) -> float:
        return max(caption.end for caption in self.captions)

    @property
    def text(self) -> str:
        # Caption records retain exact original text, including whitespace.
        return "\n".join(caption.text for caption in self.captions)


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    topic: str = Field(min_length=1, max_length=200)
    recommendation: Literal["WATCH", "SKIM", "SKIP"]
    reason: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0, le=1)

    @field_validator("topic", "reason")
    @classmethod
    def nonempty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must contain meaningful text")
        return value.strip()

    @model_validator(mode="after")
    def conservative_skip(self):
        if self.recommendation == "SKIP" and self.confidence < 0.8:
            self.recommendation = "SKIM"
            suffix = " Low-confidence SKIP was changed to SKIM to avoid missing useful material."
            self.reason = self.reason[:1000 - len(suffix)] + suffix
        return self


class AnalyzedSegment(Classification):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    youtube_url: str

    @model_validator(mode="after")
    def valid_interval(self):
        if self.end < self.start:
            raise ValueError("end must not precede start")
        return self


class AnalysisResult(BaseModel):
    video_id: str = Field(pattern=r"^[A-Za-z0-9_-]{11}$")
    model: str
    max_minutes: float | None
    truncated: bool
    warnings: list[str] = Field(default_factory=lambda: [VISUAL_WARNING])
    segments: list[AnalyzedSegment] = Field(min_length=1)

    @model_validator(mode="after")
    def chronological(self):
        if any(b.start < a.start for a, b in zip(self.segments, self.segments[1:])):
            raise ValueError("segments must be chronological")
        return self
