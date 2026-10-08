"""Command-line entry point for AI Lecture Skipper."""

import argparse
import math
from pathlib import Path
import sys

from ai_lecture_skipper.analyzer import DEFAULT_MODEL
from ai_lecture_skipper.errors import LectureSkipperError
from ai_lecture_skipper.output import save_reports, summary
from ai_lecture_skipper.pipeline import analyze_lecture


def positive_float(value):
    try:
        number = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive finite number") from error
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a positive finite number")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description="Analyze a YouTube lecture using local Ollama; save JSON and Markdown reports.")
    parser.add_argument("url", nargs="?", help="YouTube URL or video ID (prompts if omitted)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Installed model (default: {DEFAULT_MODEL})")
    parser.add_argument("--languages", nargs="+", default=["en"], help="Caption languages in preference order")
    parser.add_argument("--chunk-seconds", type=positive_float, default=300, help="Target duration (default: 300 seconds; context limits may split sooner)")
    window = parser.add_mutually_exclusive_group()
    window.add_argument("--max-minutes", type=positive_float, default=15, help="Analysis window (default: first 15 minutes)")
    window.add_argument("--full", action="store_true", help="Analyze the full lecture")
    parser.add_argument("--timeout-seconds", type=positive_float, default=600, help="Ollama request timeout (default: 600 seconds)")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"), help="Report directory (default: outputs)")
    parser.add_argument("--output", type=Path, help="Custom .json report path; Markdown uses the same filename with .md")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of the readable summary")
    args = parser.parse_args(argv)
    if args.output and args.output.suffix.lower() != ".json":
        parser.error("--output must end in .json")
    try:
        value = args.url
        if value is None:
            print("YouTube lecture URL: ", end="", file=sys.stderr, flush=True)
            value = input()
        result = analyze_lecture(
            value, languages=args.languages, model=args.model,
            chunk_seconds=args.chunk_seconds, max_minutes=None if args.full else args.max_minutes,
            timeout=args.timeout_seconds,
            progress=lambda message: print(message, file=sys.stderr, flush=True),
        )
        json_path, markdown_path = save_reports(result, args.output_dir, args.output)
        print(result.model_dump_json(indent=2) if args.json else summary(result))
        print(f"Saved JSON: {json_path}\nSaved Markdown: {markdown_path}", file=sys.stderr)
        return 0
    except (EOFError, KeyboardInterrupt):
        print("Analysis cancelled.", file=sys.stderr)
        return 130
    except LectureSkipperError as error:
        print(f"Analysis failed: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"Could not save reports: {error}. Choose a writable --output-dir and try again.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
