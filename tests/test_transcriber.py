import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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

    @patch.object(transcriber, "_transcribe_file_api", return_value="cloud transcript")
    @patch.object(transcriber, "_get_model")
    def test_auto_uses_api_before_loading_local_model(self, get_model, api_transcribe):
        with patch.object(transcriber, "TRANSCRIPTION_BACKEND", "auto"), patch.dict(
            os.environ, {"OPENAI_API_KEY": "test-key"}
        ):
            result = transcriber.transcribe_file(str(self.audio_path))

        self.assertEqual(result, "cloud transcript")
        api_transcribe.assert_called_once_with(self.audio_path, "openai", "test-key")
        get_model.assert_not_called()

    @patch.object(transcriber, "_transcribe_file_api", return_value="free transcript")
    @patch.object(transcriber, "_get_model")
    def test_auto_prefers_free_groq_key_over_openai(self, get_model, api_transcribe):
        env = {"OPENAI_API_KEY": "paid-key", "GROQ_API_KEY": "free-key"}
        with patch.object(transcriber, "TRANSCRIPTION_BACKEND", "auto"), patch.dict(
            os.environ, env
        ):
            result = transcriber.transcribe_file(str(self.audio_path))

        self.assertEqual(result, "free transcript")
        api_transcribe.assert_called_once_with(self.audio_path, "groq", "free-key")
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

    @patch.object(transcriber, "_local_whisper_available", return_value=True)
    @patch.object(transcriber, "_transcribe_file_local", return_value="local transcript")
    @patch.object(transcriber, "_transcribe_file_api")
    def test_credits_error_falls_back_to_local_whisper(
        self, api_transcribe, local_transcribe, _available
    ):
        api_transcribe.side_effect = transcriber.InsufficientCreditsError(
            transcriber._CREDITS_ERROR_MESSAGE
        )
        with patch.object(transcriber, "TRANSCRIPTION_BACKEND", "openai"), patch.dict(
            os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True
        ):
            result = transcriber.transcribe_file(str(self.audio_path))

        self.assertEqual(result, "local transcript")
        api_transcribe.assert_called_once()
        local_transcribe.assert_called_once()

    @patch.object(transcriber, "_local_whisper_available", return_value=False)
    @patch.object(transcriber, "_transcribe_file_api")
    def test_credits_error_without_local_whisper_surfaces_actionable_message(
        self, api_transcribe, _available
    ):
        api_transcribe.side_effect = transcriber.InsufficientCreditsError(
            transcriber._CREDITS_ERROR_MESSAGE
        )
        with patch.object(transcriber, "TRANSCRIPTION_BACKEND", "openai"), patch.dict(
            os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True
        ):
            with self.assertRaisesRegex(
                transcriber.TranscriptionError, "no credits remaining"
            ):
                transcriber.transcribe_file(str(self.audio_path))
            with self.assertRaisesRegex(
                transcriber.TranscriptionError, "TRANSCRIPTION_BACKEND=local"
            ):
                transcriber.transcribe_file(str(self.audio_path))

    def test_is_insufficient_credits_error_detects_quota_errors(self):
        class QuotaError(Exception):
            status_code = 429

            def __str__(self):
                return (
                    "Error code: 429 - {'error': {'code': 'insufficient_quota', "
                    "'message': 'You exceeded your current quota, please check "
                    "your plan and billing details.'}}"
                )

        class RateLimitError(Exception):
            status_code = 429

            def __str__(self):
                return "Error code: 429 - {'error': {'type': 'rate_limit_exceeded'}}"

        self.assertTrue(transcriber._is_insufficient_credits_error(QuotaError()))
        self.assertFalse(transcriber._is_insufficient_credits_error(RateLimitError()))

    @patch.object(transcriber, "_local_whisper_available", return_value=False)
    @patch.object(transcriber, "_get_model")
    def test_local_backend_without_whisper_gives_clear_error(self, get_model, _available):
        with patch.object(transcriber, "TRANSCRIPTION_BACKEND", "local"), patch.dict(
            os.environ, {}, clear=True
        ):
            with self.assertRaisesRegex(
                transcriber.TranscriptionError, "openai-whisper"
            ):
                transcriber.transcribe_file(str(self.audio_path))

        get_model.assert_not_called()


    @patch.object(transcriber, "_transcribe_file_api", return_value="groq transcript")
    def test_groq_backend_uses_groq_key(self, api_transcribe):
        with patch.object(transcriber, "TRANSCRIPTION_BACKEND", "groq"), patch.dict(
            os.environ, {"GROQ_API_KEY": "gk-key"}
        ):
            result = transcriber.transcribe_file(str(self.audio_path))

        self.assertEqual(result, "groq transcript")
        api_transcribe.assert_called_once_with(self.audio_path, "groq", "gk-key")

    def test_groq_backend_requires_groq_key(self):
        with patch.object(transcriber, "TRANSCRIPTION_BACKEND", "groq"), patch.dict(
            os.environ, {}, clear=True
        ):
            with self.assertRaisesRegex(transcriber.TranscriptionError, "GROQ_API_KEY"):
                transcriber.transcribe_file(str(self.audio_path))

    @patch.object(transcriber, "_local_whisper_available", return_value=False)
    @patch.object(transcriber, "_transcribe_file_api")
    def test_credits_error_falls_back_to_configured_free_backend(
        self, api_transcribe, _available
    ):
        def side_effect(path, backend, key):
            if backend == "openai":
                raise transcriber.InsufficientCreditsError(
                    transcriber._CREDITS_ERROR_MESSAGE
                )
            return "groq transcript"

        api_transcribe.side_effect = side_effect
        env = {"OPENAI_API_KEY": "paid-key", "GROQ_API_KEY": "free-key"}
        with patch.object(transcriber, "TRANSCRIPTION_BACKEND", "openai"), patch.dict(
            os.environ, env
        ):
            result = transcriber.transcribe_file(str(self.audio_path))

        self.assertEqual(result, "groq transcript")
        calls = [c.args[1] for c in api_transcribe.call_args_list]
        self.assertEqual(calls, ["openai", "groq"])


class CloudEntrypointTests(unittest.TestCase):
    def test_cloud_entrypoint_defaults_to_auto_free_tier_first(self):
        with patch.dict(os.environ, {}, clear=True):
            sys.modules.pop("macpocket.cloud", None)
            import macpocket.cloud  # noqa: F401

            self.assertEqual(os.environ["TRANSCRIPTION_BACKEND"], "auto")

    def test_cloud_entrypoint_preserves_explicit_override(self):
        with patch.dict(os.environ, {"TRANSCRIPTION_BACKEND": "local"}, clear=True):
            sys.modules.pop("macpocket.cloud", None)
            import macpocket.cloud  # noqa: F401

            self.assertEqual(os.environ["TRANSCRIPTION_BACKEND"], "local")


if __name__ == "__main__":
    unittest.main()
