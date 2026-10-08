import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from ollama import ResponseError
from pydantic import ValidationError
from youtube_transcript_api._errors import NoTranscriptFound, RequestBlocked, TranscriptsDisabled

import main
from ai_lecture_skipper import analyze_lecture
from ai_lecture_skipper.analyzer import LocalAnalyzer
from ai_lecture_skipper.errors import LectureSkipperError
from ai_lecture_skipper.models import AnalysisResult, AnalyzedSegment, Caption, Classification
from ai_lecture_skipper.output import markdown_report, save_reports, timestamp
from ai_lecture_skipper.segmentation import limit_transcript, segment_transcript
from ai_lecture_skipper.youtube import fetch_transcript, parse_video_id

VIDEO_ID = "dQw4w9WgXcQ"
VALID_CLASSIFICATION = dict(topic="Recurrences", recommendation="WATCH", reason="New definition and proof.", confidence=0.9)


def caption(start=0, duration=2, text="A new concept."):
    return Caption(start=start, duration=duration, text=text)


def result():
    return AnalysisResult(video_id=VIDEO_ID, model="qwen3:4b-instruct", max_minutes=15,
                          truncated=True, segments=[AnalyzedSegment(
                              **VALID_CLASSIFICATION, start=600, end=900,
                              youtube_url=f"https://www.youtube.com/watch?v={VIDEO_ID}&t=600s")])


@pytest.mark.parametrize("url", [
    f"https://www.youtube.com/watch?v={VIDEO_ID}&list=abc&t=20",
    f"https://youtu.be/{VIDEO_ID}?si=test", f"https://m.youtube.com/watch?v={VIDEO_ID}",
    f"https://youtube.com/embed/{VIDEO_ID}", f"https://youtube.com/live/{VIDEO_ID}",
])
def test_url_variants(url):
    assert parse_video_id(url) == VIDEO_ID


@pytest.mark.parametrize("url", ["", "https://youtube.com/playlist?list=x",
    f"https://evil.test/watch?v={VIDEO_ID}", "https://[bad", "https://youtu.be/invalid"])
def test_invalid_url(url):
    with pytest.raises(LectureSkipperError):
        parse_video_id(url)


def test_lossless_segmentation_including_whitespace_and_empty_captions():
    source = [caption(0, 2, "  original \n text  "), caption(2, 1, ""),
              caption(3, 297, "second"), caption(300, 2, "third")]
    chunks = segment_transcript(source)
    assert [c for chunk in chunks for c in chunk.captions] == source
    assert [(c.start, c.end) for c in chunks] == [(0, 300), (300, 302)]
    assert chunks[0].captions[0].text == "  original \n text  "


def test_context_limit_preserves_text_and_timestamps():
    source = [caption(0, 1, "a" * 8), caption(1, 1, "b" * 8), caption(2, 1, "c" * 8)]
    chunks = segment_transcript(source, max_chars=17)
    assert [len(c.text.encode("utf-8")) for c in chunks] == [17, 8]
    assert [c for chunk in chunks for c in chunk.captions] == source
    with pytest.raises(LectureSkipperError, match="context limit"):
        segment_transcript([caption(text="x" * 18)], max_chars=17)


def test_short_lecture_and_unicode_byte_bound():
    short = [caption(0, 9.25, "Example"), caption(9.25, 4, "Proof")]
    assert len(segment_transcript(short)) == 1
    assert segment_transcript(short)[0].end == 13.25
    chunks = segment_transcript([caption(0, text="éé"), caption(2, text="éé")], max_chars=5)
    assert len(chunks) == 2


def test_time_window_keeps_boundary_caption_whole():
    source = [caption(0), caption(899, 5, "complete boundary caption"), caption(900)]
    selected, truncated = limit_transcript(source, 15)
    assert selected == source[:2]
    assert selected[-1].end == 904
    assert truncated
    assert limit_transcript(source, None) == (source, False)


@pytest.mark.parametrize("limit", [0, -1, float("inf"), float("nan")])
def test_invalid_limits(limit):
    with pytest.raises(LectureSkipperError):
        segment_transcript([caption()], seconds=limit)
    with pytest.raises(LectureSkipperError):
        limit_transcript([caption()], limit)


def test_out_of_order_source():
    with pytest.raises(LectureSkipperError, match="out of order"):
        segment_transcript([caption(5), caption(4)])


@pytest.mark.parametrize("changes", [
    {"recommendation": "MAYBE"}, {"topic": "   "}, {"reason": ""}, {"confidence": True},
    {"confidence": 1.1}, {"confidence": "0.9"}, {"confidence": float("nan")}, {"start": 999},
])
def test_llm_schema_rejects_invalid_fields(changes):
    with pytest.raises(ValidationError):
        Classification.model_validate({**VALID_CLASSIFICATION, **changes})


def test_conservative_skip_and_nonmutation():
    original = {**VALID_CLASSIFICATION, "recommendation": "SKIP", "confidence": 0.3}
    validated = Classification.model_validate(original)
    assert validated.recommendation == "SKIM"
    assert "Low-confidence" in validated.reason
    assert original["recommendation"] == "SKIP"
    assert Classification.model_validate({**original, "confidence": 0.95}).recommendation == "SKIP"


def test_conservative_skip_keeps_reason_within_schema():
    validated = Classification.model_validate({**VALID_CLASSIFICATION, "recommendation": "SKIP",
                                               "confidence": 0.2, "reason": "x" * 1000})
    assert len(validated.reason) <= 1000
    assert Classification.model_validate(validated.model_dump()) == validated


def test_transcript_sdk_fetch_preserves_source(monkeypatch):
    api = MagicMock()
    source = [SimpleNamespace(start=1.5, duration=2.25, text="  text  ")]
    api.return_value.fetch.return_value = source
    monkeypatch.setattr("ai_lecture_skipper.youtube.YouTubeTranscriptApi", api)
    captions = fetch_transcript(VIDEO_ID)
    assert captions == [caption(1.5, 2.25, "  text  ")]
    api.return_value.fetch.assert_called_once_with(VIDEO_ID, languages=("en",))


@pytest.mark.parametrize("error, match", [
    (TranscriptsDisabled(VIDEO_ID), "No captions"),
    (NoTranscriptFound(VIDEO_ID, ["en"], []), "No captions"),
    (RequestBlocked(VIDEO_ID), "blocked"),
])
def test_transcript_service_errors(monkeypatch, error, match):
    api = MagicMock()
    api.return_value.fetch.side_effect = error
    monkeypatch.setattr("ai_lecture_skipper.youtube.YouTubeTranscriptApi", api)
    with pytest.raises(LectureSkipperError, match=match):
        fetch_transcript(VIDEO_ID)


def test_ollama_schema_and_source_timestamps(monkeypatch):
    client = MagicMock()
    client.return_value.chat.return_value.message.content = json.dumps(VALID_CLASSIFICATION)
    monkeypatch.setattr("ai_lecture_skipper.analyzer.Client", client)
    analyzer = LocalAnalyzer()
    analyzer.check_ready()
    chunk = segment_transcript([caption(6.5, 3, "New proof")])[0]
    segment = analyzer.analyze_chunk(chunk, VIDEO_ID)
    assert (segment.start, segment.end) == (6.5, 9.5)
    assert segment.youtube_url.endswith("&t=6s")
    kwargs = client.return_value.chat.call_args.kwargs
    assert kwargs["format"] == Classification.model_json_schema()
    assert kwargs["options"]["num_ctx"] == 4096
    assert kwargs["think"] is False
    client.return_value.show.assert_called_once_with("qwen3:4b-instruct")


def test_empty_caption_chunk_does_not_call_model(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr("ai_lecture_skipper.analyzer.Client", client)
    from ai_lecture_skipper.models import TranscriptChunk
    chunk = TranscriptChunk(captions=[caption(text=" ")])
    segment = LocalAnalyzer().analyze_chunk(chunk, VIDEO_ID)
    assert segment.recommendation == "SKIM"
    assert "visual" in segment.reason
    client.return_value.chat.assert_not_called()


def test_cloud_model_is_rejected(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr("ai_lecture_skipper.analyzer.Client", client)
    with pytest.raises(LectureSkipperError, match="remote inference"):
        LocalAnalyzer(model="example-cloud").check_ready()
    client.return_value.show.return_value.remote_host = "https://ollama.com"
    with pytest.raises(LectureSkipperError, match="remote inference"):
        LocalAnalyzer(model="custom-alias").check_ready()


@pytest.mark.parametrize("content", ["not json", "{}", '["WATCH"]', '{"start": 900}'])
def test_bad_model_json(monkeypatch, content):
    client = MagicMock()
    client.return_value.chat.return_value.message.content = content
    monkeypatch.setattr("ai_lecture_skipper.analyzer.Client", client)
    with pytest.raises(LectureSkipperError, match="invalid structured output"):
        LocalAnalyzer().analyze_chunk(segment_transcript([caption()])[0], VIDEO_ID)


@pytest.mark.parametrize("error, match", [
    (ConnectionError("refused"), "ollama serve"),
    (ResponseError("missing", status_code=404), "ollama pull"),
    (httpx.ReadTimeout("too slow"), "timeout-seconds"),
    (ResponseError("out of memory", status_code=500), "server logs"),
])
def test_model_service_errors(monkeypatch, error, match):
    client = MagicMock()
    client.return_value.show.side_effect = error
    monkeypatch.setattr("ai_lecture_skipper.analyzer.Client", client)
    with pytest.raises(LectureSkipperError, match=match):
        LocalAnalyzer().check_ready()


def test_pipeline_default_window_and_order(monkeypatch):
    source = [caption(0), caption(300), caption(600), caption(900)]
    monkeypatch.setattr("ai_lecture_skipper.pipeline.fetch_transcript", lambda *args: source)
    local = MagicMock()
    local.return_value.analyze_chunk.side_effect = lambda chunk, vid: AnalyzedSegment(
        **VALID_CLASSIFICATION, start=chunk.start, end=chunk.end,
        youtube_url=f"https://www.youtube.com/watch?v={vid}&t={int(chunk.start)}s")
    monkeypatch.setattr("ai_lecture_skipper.pipeline.LocalAnalyzer", local)
    analyzed = analyze_lecture(VIDEO_ID)
    assert [s.start for s in analyzed.segments] == [0, 300, 600]
    assert analyzed.truncated
    assert local.return_value.analyze_chunk.call_count == 3
    assert len(analyze_lecture(VIDEO_ID, max_minutes=None).segments) == 4


def test_reports_are_valid_and_clickable(tmp_path):
    analyzed = result()
    paths = save_reports(analyzed, tmp_path)
    restored = AnalysisResult.model_validate_json(paths[0].read_text(encoding="utf-8"))
    assert restored == analyzed
    markdown = paths[1].read_text(encoding="utf-8")
    assert f"[10:00-15:00]({analyzed.segments[0].youtube_url})" in markdown
    assert "Transcript-only" in markdown
    assert "--full" in markdown
    analyzed.segments[0].topic = "Text | [link] <script>"
    escaped = markdown_report(analyzed)
    assert "Text &#124; \\[link\\] &lt;script&gt;" in escaped
    assert timestamp(3661) == "1:01:01"


def test_cli_summary_and_default_files(monkeypatch, tmp_path, capsys):
    pipeline = MagicMock(return_value=result())
    monkeypatch.setattr(main, "analyze_lecture", pipeline)
    assert main.main([VIDEO_ID, "--output-dir", str(tmp_path)]) == 0
    captured = capsys.readouterr()
    assert "[WATCH] Recurrences" in captured.out
    assert "Saved Markdown" in captured.err
    assert pipeline.call_args.kwargs["max_minutes"] == 15
    assert (tmp_path / f"{VIDEO_ID}.json").exists()
    assert (tmp_path / f"{VIDEO_ID}.md").exists()


def test_cli_json_full_and_custom_output(monkeypatch, tmp_path, capsys):
    pipeline = MagicMock(return_value=result())
    monkeypatch.setattr(main, "analyze_lecture", pipeline)
    output = tmp_path / "custom.json"
    assert main.main([VIDEO_ID, "--full", "--json", "--output", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["segments"][0]["recommendation"] == "WATCH"
    assert pipeline.call_args.kwargs["max_minutes"] is None
    assert output.with_suffix(".md").exists()


def test_cli_service_failure_does_not_write_reports(monkeypatch, tmp_path, capsys):
    pipeline = MagicMock(side_effect=LectureSkipperError("Start ollama serve"))
    monkeypatch.setattr(main, "analyze_lecture", pipeline)
    assert main.main([VIDEO_ID, "--output-dir", str(tmp_path)]) == 1
    assert "ollama serve" in capsys.readouterr().err
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("args", [["--max-minutes", "nan"], ["--chunk-seconds", "0"],
                                  ["--full", "--max-minutes", "2"], ["--output", "bad.md"]])
def test_cli_rejects_invalid_options(args):
    with pytest.raises(SystemExit) as error:
        main.main([VIDEO_ID, *args])
    assert error.value.code == 2
