 (cd "$(git rev-parse --show-toplevel)" && printf '%s' 'diff --git a/README.md b/README.md
index 57a9de06e0abfa589ae3fd2832606118f5c90145..65cada8fde61794346ca20e274b94acfa54e6b59 100644
--- a/README.md
+++ b/README.md
@@ -200,50 +200,58 @@ Requires an API key set via the `OPENAI_API_KEY` environment variable
 ```bash
 export OPENAI_API_KEY="sk-..."
 python main.py --backend openai
 ```
 
 ## Whisper model sizes & performance
 
 | Model | Relative speed | Notes |
 |---|---|---|
 | `tiny` | fastest | Lower accuracy, good for quick tests |
 | `base` | fast | Default — good balance for most meetings |
 | `small` | moderate | Better accuracy, still reasonably fast |
 | `medium` | slow | High accuracy, needs more RAM/CPU |
 | `large` | slowest | Best accuracy, requires significant resources |
 
 By default, MacPocket runs Whisper with `fp16=False` for compatibility
 with Intel Macs (fp16 on CPU can be unstable). If you'\''re on Apple
 Silicon (M1/M2/M3), pass `--fp16` for a speed boost:
 
 ```bash
 python main.py --model small --fp16
 ```
 
 ## Troubleshooting
 
+**Hosted `/upload-audio` requests return 502**
+Cloud workers can time out or run out of memory while downloading and running
+the local Whisper model. Configure `OPENAI_API_KEY` in the deployment. The
+default `TRANSCRIPTION_BACKEND=auto` uses the OpenAI transcription API when a
+key is available, before importing or loading local Whisper. Local installs
+without a key continue to run Whisper on-device. You can override the choice
+with `TRANSCRIPTION_BACKEND=local` or `TRANSCRIPTION_BACKEND=openai`.
+
 **"No input devices found" / microphone not detected**
 Check **System Settings → Privacy & Security → Microphone** and make
 sure Terminal (or whichever app you'\''re running Python from) has
 permission to access the microphone.
 
 **BlackHole device not found**
 Run `brew install blackhole-2ch`, then restart Terminal. MacPocket will
 also print this instruction automatically if it detects the issue.
 
 **Ollama connection errors**
 Make sure the Ollama app/daemon is running and you'\''ve pulled the model:
 `ollama pull llama3.2`.
 
 **Whisper is slow**
 Try a smaller model (`--model tiny` or `--model base`), or add `--fp16`
 if you'\''re on Apple Silicon.
 
 ## Project structure
 
 ```
 macpocket/
 ├── main.py          # CLI entry point — orchestrates record → transcribe → summarize → save
 ├── recorder.py       # Audio capture (sounddevice), device resolution, BlackHole handling
 ├── transcriber.py    # Local Whisper transcription
 ├── summarizer.py      # Ollama / OpenAI summarization backends
' | git apply --3way)
