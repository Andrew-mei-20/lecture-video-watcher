import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lecture_skipper import analyze, chunk_transcript, parse_video_id, validate_classification


class PipelineTests(unittest.TestCase):
    def test_url_forms_and_rejected_hosts(self):
        for url in ("dQw4w9WgXcQ", "https://youtu.be/dQw4w9WgXcQ?t=1", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://youtube.com/shorts/dQw4w9WgXcQ"):
            self.assertEqual(parse_video_id(url), "dQw4w9WgXcQ")
        for url in ("https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ", "https://youtu.be/short", "file://youtube.com/watch?v=dQw4w9WgXcQ"):
            with self.assertRaises(ValueError):
                parse_video_id(url)

    def test_chunks_preserve_all_captions_and_bounds(self):
        snippets = [SimpleNamespace(start=t, duration=2, text="word") for t in (0, 2, 300)]
        chunks = chunk_transcript(snippets)
        self.assertEqual([c["text"] for c in chunks], ["word word", "word"])
        self.assertEqual([(c["start"], c["end"]) for c in chunks], [(0, 4), (300, 302)])
        self.assertEqual(len(chunk_transcript(snippets, max_chars=5)), 3)
        with self.assertRaises(ValueError):
            chunk_transcript([])
        with self.assertRaises(ValueError):
            chunk_transcript([SimpleNamespace(start=float("nan"), duration=2, text="bad")])

    def test_classification_safety(self):
        data = dict(topic="Review", reason="Repeated content", recommendation="SKIP", confidence=0.5)
        self.assertEqual(validate_classification(data)["recommendation"], "SKIM")
        for confidence in (True, -1, 2, float("nan"), "0.5"):
            with self.assertRaises(ValueError):
                validate_classification({**data, "confidence": confidence})
        with self.assertRaises(ValueError):
            validate_classification({**data, "recommendation": "OTHER"})

    @patch("ai_lecture_skipper.analyzer.Client")
    @patch("ai_lecture_skipper.youtube.YouTubeTranscriptApi")
    def test_pipeline_service_boundaries(self, transcript_api, client):
        transcript_api.return_value.fetch.return_value = [SimpleNamespace(start=10.5, duration=5, text="A definition")]
        client.return_value.chat.return_value.message.content = json.dumps(dict(topic="Definition", reason="New concept", recommendation="WATCH", confidence=0.9))
        result = analyze("dQw4w9WgXcQ", ["en"])
        self.assertEqual(result["segments"][0]["start"], 10.5)
        self.assertTrue(result["segments"][0]["url"].endswith("&t=10s"))
        client.assert_called_once_with(host="http://localhost:11434", timeout=600, trust_env=False)
        transcript_api.return_value.fetch.assert_called_once_with("dQw4w9WgXcQ", languages=["en"])


if __name__ == "__main__":
    unittest.main()
