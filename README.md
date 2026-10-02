## Whisper model sizes & performance

| Model | Relative speed | Notes |
|---|---|---|
| `tiny` | fastest | Lower accuracy, good for quick tests |
| `base` | fast | Default — good balance for most meetings |
| `small` | moderate | Better accuracy, still reasonably fast |
| `medium` | slow | High accuracy, needs more RAM/CPU |
| `large` | slowest | Best accuracy, requires significant resources |

By default, MacPocket runs Whisper with `fp16=False` for compatibility
with Intel Macs (fp16 on CPU can be unstable). If you're on Apple
Silicon (M1/M2/M3), pass `--fp16` for a speed boost:

```bash
python main.py --model small --fp16
```

## Troubleshooting

**Hosted `/upload-audio` requests return 502**
Cloud workers can time out or run out of memory while downloading and running
the local Whisper model. The checked-in FastAPI Cloud and Procfile entry points
use `macpocket.cloud`, which selects API transcription without installing the
large local audio/ML dependency stack. Configure `OPENAI_API_KEY` in the
deployment and redeploy. Local installs continue to use `macpocket.main` and
run Whisper on-device. You can override either choice with
`TRANSCRIPTION_BACKEND=local`, `auto`, or `openai`.

**"No input devices found" / microphone not detected**
Check **System Settings → Privacy & Security → Microphone** and make
sure Terminal (or whichever app you're running Python from) has
permission to access the microphone.

**BlackHole device not found**
Run `brew install blackhole-2ch`, then restart Terminal. MacPocket will
also print this instruction automatically if it detects the issue.

**Ollama connection errors**
Make sure the Ollama app/daemon is running and you've pulled the model:
`ollama pull llama3.2`.

**Whisper is slow**
Try a smaller model (`--model tiny` or `--model base`), or add `--fp16`
if you're on Apple Silicon.

## Project structure

```
macpocket/
├── main.py          # CLI entry point — orchestrates record → transcribe → summarize → save
├── recorder.py       # Audio capture (sounddevice), device resolution, BlackHole handling
├── transcriber.py    # Local Whisper transcription
├── summarizer.py      # Ollama / OpenAI summarization backends
├── config.py          # Defaults, paths, prompt template, constants
├── requirements.txt
├── setup.sh
└── README.md
```

## Privacy

- Audio and transcripts stay on your Mac at all times when using the
  default local transcription and summarization backends.
- Selecting OpenAI only as the summarizer sends the **transcript text** (not
  audio) to OpenAI. The resource-safe `macpocket.cloud` deployment entry point
  uses OpenAI transcription and therefore sends uploaded audio to OpenAI as
  well. Set `TRANSCRIPTION_BACKEND=local` only on a host provisioned to run
  local Whisper.
- Notes are stored locally in `~/MacPocket/Notes/`. Nothing is uploaded
  or synced anywhere by MacPocket itself.
