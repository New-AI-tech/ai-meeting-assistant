import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


PACKAGE_DIR = Path(__file__).resolve().parents[1] / "macpocket"
sys.path.insert(0, str(PACKAGE_DIR))

import transcriber


class TranscribeFileBackendTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        handle.write(b"not-empty")
        handle.close()
        self.audio_path = Path(handle.name)

    def tearDown(self):
        self.audio_path.unlink(missing_ok=True)

    @patch.object(transcriber, "_transcribe_file_openai", return_value="cloud transcript")
    @patch.object(transcriber, "_get_model")
    def test_auto_uses_api_before_loading_local_model(self, get_model, api_transcribe):
        with patch.object(transcriber, "TRANSCRIPTION_BACKEND", "auto"), patch.dict(
            os.environ, {"OPENAI_API_KEY": "test-key"}
        ):
            result = transcriber.transcribe_file(str(self.audio_path))

        self.assertEqual(result, "cloud transcript")
        api_transcribe.assert_called_once_with(self.audio_path, "test-key")
        get_model.assert_not_called()


    @patch.object(transcriber, "_get_model")
    def test_auto_without_key_uses_local_model(self, get_model):
        get_model.return_value.transcribe.return_value = {"text": " local transcript "}
        with patch.object(transcriber, "TRANSCRIPTION_BACKEND", "auto"), patch.dict(
            os.environ, {}, clear=True
        ):
            result = transcriber.transcribe_file(str(self.audio_path))

        self.assertEqual(result, "local transcript")
        get_model.assert_called_once_with("tiny")

    @patch.object(transcriber, "_get_model")
    def test_openai_backend_requires_key_without_loading_model(self, get_model):
        with patch.object(transcriber, "TRANSCRIPTION_BACKEND", "openai"), patch.dict(
            os.environ, {}, clear=True
        ):
            with self.assertRaisesRegex(transcriber.TranscriptionError, "OPENAI_API_KEY"):
                transcriber.transcribe_file(str(self.audio_path))

        get_model.assert_not_called()


class CloudEntrypointTests(unittest.TestCase):
    def test_cloud_entrypoint_defaults_to_groq(self):
        with patch.dict(os.environ, {}, clear=True):
            sys.modules.pop("macpocket.cloud", None)
            import macpocket.cloud  # noqa: F401

            self.assertEqual(os.environ["TRANSCRIPTION_BACKEND"], "groq")

    def test_cloud_entrypoint_replaces_stale_openai_override(self):
        with patch.dict(os.environ, {"TRANSCRIPTION_BACKEND": "openai"}, clear=True):
            sys.modules.pop("macpocket.cloud", None)
            import macpocket.cloud  # noqa: F401

            self.assertEqual(os.environ["TRANSCRIPTION_BACKEND"], "groq")


class OpenAIErrorTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        handle.write(b"not-empty")
        handle.close()
        self.audio_path = Path(handle.name)

    def tearDown(self):
        self.audio_path.unlink(missing_ok=True)

    def test_exhausted_credits_raise_actionable_quota_error(self):
        error = RuntimeError("sensitive provider error")
        error.status_code = 429
        error.body = {
            "error": {
                "type": "insufficient_quota",
                "code": "credit_balance_exhausted",
            }
        }
        client = MagicMock()
        client.audio.transcriptions.create.side_effect = error

        with patch.dict(sys.modules, {"openai": MagicMock(OpenAI=lambda **_: client)}):
            with self.assertRaisesRegex(
                transcriber.TranscriptionQuotaError, "no credits remaining"
            ):
                transcriber._transcribe_file_openai(self.audio_path, "test-key")

    def test_temporary_429_is_distinct_from_exhausted_credits(self):
        error = RuntimeError("rate limited")
        error.status_code = 429
        error.body = {"error": {"code": "rate_limit_exceeded"}}
        client = MagicMock()
        client.audio.transcriptions.create.side_effect = error

        with patch.dict(sys.modules, {"openai": MagicMock(OpenAI=lambda **_: client)}):
            with self.assertRaises(transcriber.TranscriptionRateLimitError):
                transcriber._transcribe_file_openai(self.audio_path, "test-key")


class AssemblyAIBackendTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        handle.write(b"not-empty")
        handle.close()
        self.audio_path = Path(handle.name)

    def tearDown(self):
        self.audio_path.unlink(missing_ok=True)

    @patch.object(transcriber, "_transcribe_file_assemblyai", return_value="text")
    @patch.object(transcriber, "_get_model")
    def test_auto_prefers_assemblyai_when_key_is_configured(
        self, get_model, assemblyai_transcribe
    ):
        with patch.object(transcriber, "TRANSCRIPTION_BACKEND", "auto"), patch.dict(
            os.environ, {"ASSEMBLYAI_API_KEY": "test-key"}, clear=True
        ):
            result = transcriber.transcribe_file(str(self.audio_path))

        self.assertEqual(result, "text")
        assemblyai_transcribe.assert_called_once_with(self.audio_path, "test-key")
        get_model.assert_not_called()

    @patch.object(transcriber, "_get_model")
    def test_assemblyai_backend_requires_key(self, get_model):
        with patch.object(
            transcriber, "TRANSCRIPTION_BACKEND", "assemblyai"
        ), patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                transcriber.TranscriptionError, "ASSEMBLYAI_API_KEY"
            ):
                transcriber.transcribe_file(str(self.audio_path))

        get_model.assert_not_called()


class GroqBackendTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        handle.write(b"not-empty")
        handle.close()
        self.audio_path = Path(handle.name)

    def tearDown(self):
        self.audio_path.unlink(missing_ok=True)

    @patch.object(transcriber, "_transcribe_file_groq", return_value="groq text")
    @patch.object(transcriber, "_get_model")
    def test_auto_prefers_groq_when_key_is_configured(
        self, get_model, groq_transcribe
    ):
        with patch.object(transcriber, "TRANSCRIPTION_BACKEND", "auto"), patch.dict(
            os.environ,
            {"GROQ_API_KEY": "test-key", "ASSEMBLYAI_API_KEY": "other-key"},
            clear=True,
        ):
            result = transcriber.transcribe_file(str(self.audio_path))

        self.assertEqual(result, "groq text")
        groq_transcribe.assert_called_once_with(self.audio_path, "test-key")
        get_model.assert_not_called()

    @patch.object(transcriber, "_get_model")
    def test_groq_backend_requires_key(self, get_model):
        with patch.object(
            transcriber, "TRANSCRIPTION_BACKEND", "groq"
        ), patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(transcriber.TranscriptionError, "GROQ_API_KEY"):
                transcriber.transcribe_file(str(self.audio_path))

        get_model.assert_not_called()

    def test_groq_sdk_transcribes_with_hosted_whisper(self):
        client = MagicMock()
        client.audio.transcriptions.create.return_value.text = " Groq transcript "
        groq_client = MagicMock(return_value=client)

        with patch.dict(sys.modules, {"groq": MagicMock(Groq=groq_client)}):
            result = transcriber._transcribe_file_groq(self.audio_path, "test-key")

        self.assertEqual(result, "Groq transcript")
        groq_client.assert_called_once_with(api_key="test-key")
        kwargs = client.audio.transcriptions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "whisper-large-v3-turbo")
        self.assertEqual(kwargs["response_format"], "json")

if __name__ == "__main__":
    unittest.main()
