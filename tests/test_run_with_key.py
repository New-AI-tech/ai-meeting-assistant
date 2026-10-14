"""Tests for the AssemblyAI API-key launcher."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import run_with_key


class RunWithKeyTests(unittest.TestCase):
    def test_argument_key_and_audio_path_are_forwarded(self) -> None:
        observed_key = None

        def fake_run(command, check):
            nonlocal observed_key
            observed_key = os.environ.get("ASSEMBLYAI_API_KEY")
            self.assertFalse(check)
            self.assertEqual(
                command,
                [
                    run_with_key.sys.executable,
                    str(run_with_key.TRANSCRIBER_SCRIPT),
                    "meeting audio.mp3",
                ],
            )
            return SimpleNamespace(returncode=0)

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(run_with_key.subprocess, "run", side_effect=fake_run),
            patch.object(run_with_key.getpass, "getpass") as prompt,
        ):
            result = run_with_key.main(
                ["--api-key", "secret-key", "meeting audio.mp3"]
            )
            self.assertNotIn("ASSEMBLYAI_API_KEY", os.environ)

        self.assertEqual(result, 0)
        self.assertEqual(observed_key, "secret-key")
        prompt.assert_not_called()

    def test_missing_argument_prompts_without_echoing(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(
                run_with_key.getpass, "getpass", return_value="prompted-key"
            ) as prompt,
            patch.object(
                run_with_key.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=7),
            ),
        ):
            result = run_with_key.main([])

        self.assertEqual(result, 7)
        prompt.assert_called_once_with("AssemblyAI API key: ")

    def test_empty_key_does_not_start_child(self) -> None:
        with (
            patch.object(run_with_key.getpass, "getpass", return_value="  "),
            patch.object(run_with_key.subprocess, "run") as run,
        ):
            result = run_with_key.main([])

        self.assertEqual(result, 1)
        run.assert_not_called()

    def test_existing_environment_key_is_restored(self) -> None:
        with (
            patch.dict(
                os.environ, {"ASSEMBLYAI_API_KEY": "original-key"}, clear=True
            ),
            patch.object(
                run_with_key.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=0),
            ),
        ):
            result = run_with_key.main(["--api-key", "temporary-key"])
            restored_key = os.environ["ASSEMBLYAI_API_KEY"]

        self.assertEqual(result, 0)
        self.assertEqual(restored_key, "original-key")

    def test_launch_failure_restores_environment(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(
                run_with_key.subprocess, "run", side_effect=OSError("cannot execute")
            ),
        ):
            result = run_with_key.main(["--api-key", "temporary-key"])
            key_remains = "ASSEMBLYAI_API_KEY" in os.environ

        self.assertEqual(result, 1)
        self.assertFalse(key_remains)


if __name__ == "__main__":
    unittest.main()
