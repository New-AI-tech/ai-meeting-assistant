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
large local audio/ML dependency stack. Configure an API key in the deployment
(`GROQ_API_KEY` for the free Groq tier, or `OPENAI_API_KEY` for the paid
OpenAI API) and redeploy. Local installs continue to use `macpocket.main` and
run Whisper on-device. You can override either choice with
`TRANSCRIPTION_BACKEND=local`, `auto`, `openai`, `groq`, or `assembler`.

**"OpenAI transcription is unavailable ... no credits remaining"**
The OpenAI account behind your `OPENAI_API_KEY` has an exhausted API balance
(the API returns a 429 `insufficient_quota` error). Free alternatives:

1. **Use a free API tier** — MacPocket supports OpenAI-compatible
   transcription providers with free tiers:
   - Groq (recommended): create a free key at https://console.groq.com/keys,
     then set `TRANSCRIPTION_BACKEND=groq` and `GROQ_API_KEY=gsk_...`
     (uses `whisper-large-v3-turbo`; override with `GROQ_WHISPER_MODEL`).
   - AssemblerAPI: free developer account at https://www.assemblerapi.co,
     then set `TRANSCRIPTION_BACKEND=assembler` and `ASSEMBLER_API_KEY=...`
     (override the model with `ASSEMBLER_MODEL`).
2. **Run fully local for free** — on a machine with the local Whisper stack
   installed (`pip install openai-whisper`, `brew install ffmpeg`), set
   `TRANSCRIPTION_BACKEND=local`. No API costs at all.
3. Top up credits at https://platform.openai.com/account/billing.

In `auto` mode MacPocket prefers configured free-tier keys (Groq,
AssemblerAPI) over the paid OpenAI key, and if any API account runs out of
credits it automatically falls back to local Whisper when available, or to
another configured backend, before surfacing this message.

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
