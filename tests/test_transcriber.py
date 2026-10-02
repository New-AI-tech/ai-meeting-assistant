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
    def test_cloud_entrypoint_defaults_to_openai(self):
        with patch.dict(os.environ, {}, clear=True):
            sys.modules.pop("macpocket.cloud", None)
            import macpocket.cloud  # noqa: F401

            self.assertEqual(os.environ["TRANSCRIPTION_BACKEND"], "openai")

    def test_cloud_entrypoint_preserves_explicit_override(self):
        with patch.dict(os.environ, {"TRANSCRIPTION_BACKEND": "local"}, clear=True):
            sys.modules.pop("macpocket.cloud", None)
            import macpocket.cloud  # noqa: F401

            self.assertEqual(os.environ["TRANSCRIPTION_BACKEND"], "local")


if __name__ == "__main__":
    unittest.main()
