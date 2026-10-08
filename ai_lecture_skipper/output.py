"""Readable terminal summaries and JSON/Markdown reports."""

from pathlib import Path

from .models import AnalysisResult


def timestamp(seconds: float):
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes:02}:{seconds:02}"


def summary(result: AnalysisResult):
    lines = [f"AI Lecture Skipper - {result.video_id} ({result.model})"]
    for segment in result.segments:
        lines.extend([
            f"{timestamp(segment.start)}-{timestamp(segment.end)} [{segment.recommendation}] {segment.topic}",
            f"  {segment.reason}", f"  {segment.youtube_url}",
        ])
    if result.truncated:
        lines.append(f"Analysis limited to the first {result.max_minutes:g} minutes (complete captions retained). Use --full for the full lecture.")
    lines.extend(f"Note: {warning}" for warning in result.warnings)
    return "\n".join(lines)


def _escape_cell(value):
    return (value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("|", "&#124;").replace("\r", " ").replace("\n", " ")
            .replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
            .replace("*", "\\*").replace("_", "\\_").replace("`", "\\`"))


def markdown_report(result: AnalysisResult):
    lines = ["# AI Lecture Skipper", "", f"Video: [{result.video_id}](https://www.youtube.com/watch?v={result.video_id})",
             f"Model: {_escape_cell(result.model)}", ""]
    if result.max_minutes is not None:
        lines.extend([f"Analysis window: first {result.max_minutes:g} minutes; complete captions crossing the boundary are retained.", ""])
    lines.extend([f"> {warning}" for warning in result.warnings])
    lines.extend(["", "| Timestamp | Topic | Recommendation | Reason |",
                  "|---|---|---|---|"])
    for segment in result.segments:
        label = f"{timestamp(segment.start)}-{timestamp(segment.end)}"
        lines.append(f"| [{label}]({segment.youtube_url}) | {_escape_cell(segment.topic)} | {segment.recommendation} | {_escape_cell(segment.reason)} |")
    if result.truncated:
        lines.extend(["", "This report covers only the selected analysis window. Use `--full` to include the rest of the lecture."])
    return "\n".join(lines) + "\n"


def save_reports(result: AnalysisResult, output_dir=Path("outputs"), json_path=None):
    json_path = Path(json_path) if json_path else Path(output_dir) / f"{result.video_id}.json"
    if json_path.suffix.lower() != ".json":
        raise ValueError("The output path must end in .json.")
    markdown_path = json_path.with_suffix(".md")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown_report(result), encoding="utf-8")
    return json_path, markdown_path
