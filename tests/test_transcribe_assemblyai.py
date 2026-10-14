"""Unit tests for the standalone AssemblyAI transcription CLI."""

import io
import unittest
from types import SimpleNamespace
from typing import Optional, Tuple, Union
from unittest.mock import MagicMock, patch

import transcribe_assemblyai


class AssemblyAICommandTests(unittest.TestCase):
    """Exercise every success and controlled-failure branch in ``main``."""

    def setUp(self) -> None:
        self.sdk = SimpleNamespace(
            settings=SimpleNamespace(api_key=None),
            TranscriptStatus=SimpleNamespace(
                processing="processing",
                completed="completed",
                error="error",
            ),
            Transcriber=MagicMock(),
        )
        self.transcriber = self.sdk.Transcriber.return_value

    def _run(
        self,
        *,
        argv: Optional[list[str]] = None,
        file_exists: bool = True,
        api_key: Optional[str] = "test-key",
        sdk: Optional[object] = None,
    ) -> Tuple[Optional[Union[int, str]], str, str]:
        """Invoke ``main`` with all external dependencies isolated."""
        stdout = io.StringIO()
        stderr = io.StringIO()
        environment = {"ASSEMBLYAI_API_KEY": api_key} if api_key else {}
        imported_sdk = self.sdk if sdk is None else sdk

        with (
            patch.object(
                transcribe_assemblyai.importlib,
                "import_module",
                return_value=imported_sdk,
            ),
            patch.object(transcribe_assemblyai.os.path, "exists", return_value=file_exists),
            patch.dict(transcribe_assemblyai.os.environ, environment, clear=True),
            patch.object(transcribe_assemblyai.sys, "stdout", stdout),
            patch.object(transcribe_assemblyai.sys, "stderr", stderr),
        ):
            with self.assertRaises(SystemExit) as raised:
                transcribe_assemblyai.main(
                    ["meeting.mp3"] if argv is None else argv
                )

        return raised.exception.code, stdout.getvalue(), stderr.getvalue()

    def test_missing_local_file_exits_with_one(self) -> None:
        code, _, stderr = self._run(file_exists=False)

        self.assertEqual(code, 1)
        self.assertIn("audio file does not exist: meeting.mp3", stderr)
        self.transcriber.submit.assert_not_called()

    def test_missing_api_key_exits_with_one(self) -> None:
        code, _, stderr = self._run(api_key=None)

        self.assertEqual(code, 1)
        self.assertIn("ASSEMBLYAI_API_KEY is not set", stderr)
        self.transcriber.submit.assert_not_called()

    def test_missing_sdk_exits_with_controlled_error(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(
                transcribe_assemblyai.importlib,
                "import_module",
                side_effect=ModuleNotFoundError("assemblyai"),
            ),
            patch.object(transcribe_assemblyai.os.path, "exists"),
            patch.object(transcribe_assemblyai.sys, "stdout", stdout),
            patch.object(transcribe_assemblyai.sys, "stderr", stderr),
        ):
            with self.assertRaises(SystemExit) as raised:
                transcribe_assemblyai.main(["meeting.mp3"])

        self.assertEqual(raised.exception.code, 1)
        self.assertIn("pip install assemblyai", stderr.getvalue())

    def test_processing_job_is_polled_then_printed(self) -> None:
        processing = SimpleNamespace(id="job-123", status="processing")
        completed = SimpleNamespace(
            id="job-123", status="completed", text="Final transcript"
        )
        self.transcriber.submit.return_value = processing
        self.transcriber.get_transcript.return_value = completed

        with patch.object(transcribe_assemblyai.time, "sleep") as sleep:
            code, stdout, stderr = self._run()

        self.assertEqual(code, 0)
        self.assertEqual(stdout, "Final transcript\n")
        self.assertEqual(stderr, "")
        self.assertEqual(self.sdk.settings.api_key, "test-key")
        self.transcriber.submit.assert_called_once_with("meeting.mp3")
        sleep.assert_called_once_with(3)
        self.transcriber.get_transcript.assert_called_once_with("job-123")

    def test_provider_error_prints_detail_and_exits_with_one(self) -> None:
        self.transcriber.submit.return_value = SimpleNamespace(
            id="job-123", status="error", error="unsupported audio format"
        )

        code, stdout, stderr = self._run()

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("AssemblyAI transcription failed", stderr)
        self.assertIn("unsupported audio format", stderr)

    def test_omitted_path_uses_default_audio_file(self) -> None:
        self.transcriber.submit.return_value = SimpleNamespace(
            id="job-123", status="completed", text="Default file transcript"
        )

        code, stdout, stderr = self._run(argv=[])

        self.assertEqual(code, 0)
        self.assertEqual(stdout, "Default file transcript\n")
        self.assertEqual(stderr, "")
        self.transcriber.submit.assert_called_once_with("audio.mp3")

    def test_unexpected_exception_prints_traceback(self) -> None:
        self.transcriber.submit.side_effect = RuntimeError("network unavailable")

        code, _, stderr = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Traceback (most recent call last)", stderr)
        self.assertIn("network unavailable", stderr)

    def test_help_exits_with_zero_without_loading_sdk(self) -> None:
        stdout = io.StringIO()
        with (
            patch.object(transcribe_assemblyai.importlib, "import_module") as loader,
            patch.object(transcribe_assemblyai.sys, "stdout", stdout),
        ):
            with self.assertRaises(SystemExit) as raised:
                transcribe_assemblyai.main(["--help"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("usage:", stdout.getvalue())
        loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
