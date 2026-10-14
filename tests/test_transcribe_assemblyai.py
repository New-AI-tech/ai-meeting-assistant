import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import transcribe_assemblyai


class AssemblyAITranscriptionTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        handle.write(b"audio")
        handle.close()
        self.audio_path = Path(handle.name)

    def tearDown(self):
        self.audio_path.unlink(missing_ok=True)

    def _sdk(self, *, status="completed", text="hello", error=None):
        transcript = SimpleNamespace(
            id="transcript-id", status=status, text=text, error=error
        )
        transcriber = MagicMock()
        transcriber.submit.return_value = transcript
        sdk = SimpleNamespace(
            settings=SimpleNamespace(api_key=None),
            TranscriptStatus=SimpleNamespace(completed="completed", error="error"),
            Transcriber=MagicMock(return_value=transcriber),
        )
        return sdk, transcriber

    def test_returns_completed_transcript_and_configures_key(self):
        sdk, transcriber = self._sdk(text="Meeting notes")

        with patch.dict(sys.modules, {"assemblyai": sdk}):
            result = transcribe_assemblyai.transcribe_file(self.audio_path, "secret")

        self.assertEqual(result, "Meeting notes")
        self.assertEqual(sdk.settings.api_key, "secret")
        transcriber.submit.assert_called_once_with(str(self.audio_path))

    def test_polls_until_transcription_completes(self):
        sdk, transcriber = self._sdk(status="queued", text=None)
        completed = SimpleNamespace(
            id="transcript-id", status="completed", text="Done", error=None
        )
        transcriber.get_transcript.return_value = completed

        with patch.dict(sys.modules, {"assemblyai": sdk}), patch.object(
            transcribe_assemblyai.time, "sleep"
        ) as sleep:
            result = transcribe_assemblyai.transcribe_file(self.audio_path, "secret")

        self.assertEqual(result, "Done")
        sleep.assert_called_once_with(transcribe_assemblyai.POLL_INTERVAL_SECONDS)
        transcriber.get_transcript.assert_called_once_with("transcript-id")

    def test_reports_failed_transcription(self):
        sdk, _ = self._sdk(status="error", text=None, error="invalid audio")

        with patch.dict(sys.modules, {"assemblyai": sdk}):
            with self.assertRaisesRegex(RuntimeError, "invalid audio"):
                transcribe_assemblyai.transcribe_file(self.audio_path, "secret")


if __name__ == "__main__":
    unittest.main()
