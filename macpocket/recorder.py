"""
recorder.py — Audio capture logic for MacPocket.

Handles listing macOS CoreAudio input devices (via sounddevice), recording
in fixed-size chunks so memory usage stays flat during long meetings, and
gracefully finalizing the recording on CTRL+C.
"""

import sys
import time
from typing import List, Optional

import numpy as np

try:
    import sounddevice as sd
except OSError as exc:
    # sounddevice raises OSError at import time if PortAudio isn't found.
    print(
        "\n[MacPocket] Could not load the PortAudio library required by "
        "'sounddevice'.\n"
        "Install it with:\n"
        "    brew install portaudio\n"
        "then re-install the Python requirements:\n"
        "    pip install -r requirements.txt\n"
    )
    raise SystemExit(1) from exc

from config import BLACKHOLE_DEVICE_NAME, BLACKHOLE_INSTALL_CMD, CHANNELS, CHUNK_SECONDS, DTYPE, SAMPLE_RATE


class DeviceNotFoundError(Exception):
    """Raised when the requested input device cannot be located."""


class BlackHoleNotInstalledError(Exception):
    """Raised when the user asks for BlackHole but it isn't installed."""


def list_input_devices() -> List[dict]:
    """Return a list of available input-capable audio devices on macOS."""
    devices = sd.query_devices()
    input_devices = []
    for idx, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) > 0:
            input_devices.append(
                {
                    "index": idx,
                    "name": dev["name"],
                    "max_input_channels": dev["max_input_channels"],
                    "default_samplerate": dev["default_samplerate"],
                }
            )
    return input_devices


def print_device_list(devices: List[dict]) -> None:
    print("\nAvailable input devices:\n")
    for dev in devices:
        print(f"  [{dev['index']}] {dev['name']}  "
              f"({dev['max_input_channels']} ch, "
              f"{int(dev['default_samplerate'])} Hz)")
    print()


def prompt_for_device(devices: List[dict]) -> dict:
    """Interactively ask the user to choose an input device."""
    print_device_list(devices)
    while True:
        choice = input("Select a device index to record from: ").strip()
        try:
            idx = int(choice)
        except ValueError:
            print("Please enter a valid device index number.")
            continue
        match = next((d for d in devices if d["index"] == idx), None)
        if match is None:
            print("That index isn't in the list above. Try again.")
            continue
        return match


def resolve_device(device_name: Optional[str]) -> dict:
    """
    Resolve a device name (possibly partial/case-insensitive) to a device
    dict. If `device_name` is None, prompt the user interactively.

    Raises BlackHoleNotInstalledError with clear install instructions if the
    user requested BlackHole but it isn't present. Raises DeviceNotFoundError
    for any other missing device.
    """
    devices = list_input_devices()
    if not devices:
        raise DeviceNotFoundError(
            "No input-capable audio devices were found on this Mac. Check "
            "System Settings > Privacy & Security > Microphone to make sure "
            "Terminal (or your Python interpreter) has microphone access."
        )

    if device_name is None:
        return prompt_for_device(devices)

    lowered = device_name.strip().lower()
    match = next((d for d in devices if d["name"].strip().lower() == lowered), None)
    if match is None:
        # fall back to substring match, e.g. "blackhole" -> "BlackHole 2ch"
        match = next((d for d in devices if lowered in d["name"].strip().lower()), None)

    if match is not None:
        return match

    if "blackhole" in lowered:
        raise BlackHoleNotInstalledError(
            f"\n[MacPocket] Could not find the '{BLACKHOLE_DEVICE_NAME}' "
            "input device.\n\n"
            "MacPocket uses BlackHole to capture system audio (e.g. Zoom, "
            "Google Meet, or any app's playback) alongside your microphone.\n\n"
            "To install it, run:\n"
            f"    {BLACKHOLE_INSTALL_CMD}\n\n"
            "Then, in 'Audio MIDI Setup', create a Multi-Output Device that "
            "includes both your speakers and BlackHole 2ch so you can still "
            "hear the meeting while MacPocket records it. See README.md for "
            "step-by-step instructions.\n"
        )

    raise DeviceNotFoundError(
        f"No input device matching '{device_name}' was found.\n"
        f"{_format_device_names(devices)}"
    )


def _format_device_names(devices: List[dict]) -> str:
    names = "\n".join(f"  - {d['name']}" for d in devices)
    return f"Available devices:\n{names}"


class Recorder:
    """
    Records audio from a chosen input device in fixed-length chunks,
    concatenating them efficiently with numpy so memory stays bounded and
    predictable during long meetings.
    """

    def __init__(self, device_index: int, sample_rate: int = SAMPLE_RATE,
                 channels: int = CHANNELS, chunk_seconds: int = CHUNK_SECONDS):
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_seconds = chunk_seconds
        self._chunks: List[np.ndarray] = []

    def record(self, duration: Optional[float] = None) -> np.ndarray:
        """
        Record audio until `duration` seconds have elapsed, or until the
        user presses CTRL+C if `duration` is None. Returns the full
        recording as a single 1-D float32 numpy array.
        """
        print(
            f"\n[MacPocket] Recording from device index {self.device_index} "
            f"at {self.sample_rate} Hz. Press CTRL+C to stop.\n"
        )

        start_time = time.time()
        try:
            with sd.InputStream(
                device=self.device_index,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=DTYPE,
            ) as stream:
                while True:
                    if duration is not None and (time.time() - start_time) >= duration:
                        break

                    frames_to_read = int(self.chunk_seconds * self.sample_rate)
                    if duration is not None:
                        remaining = duration - (time.time() - start_time)
                        frames_to_read = min(
                            frames_to_read, max(1, int(remaining * self.sample_rate))
                        )

                    chunk, overflowed = stream.read(frames_to_read)
                    if overflowed:
                        print("[MacPocket] Warning: audio buffer overflow, "
                              "some audio may have been dropped.", file=sys.stderr)
                    self._chunks.append(chunk.copy())
                    elapsed = int(time.time() - start_time)
                    print(f"\r[MacPocket] Recording... {elapsed}s elapsed", end="", flush=True)
        except KeyboardInterrupt:
            print("\n[MacPocket] CTRL+C received — stopping recording and "
                  "saving audio buffer...")
        finally:
            print()

        return self._finalize()

    def _finalize(self) -> np.ndarray:
        if not self._chunks:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(self._chunks, axis=0)
        # Collapse to mono if a multi-channel device was used.
        if audio.ndim > 1 and audio.shape[1] > 1:
            audio = audio.mean(axis=1)
        else:
            audio = audio.reshape(-1)
        return audio.astype(np.float32)
