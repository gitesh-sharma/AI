# SNS AI

Offline-first local AI web platform for Windows, macOS, Linux and Android.

## What it is
SNS AI is a self-hosted/local web application. The browser UI talks to a local FastAPI service, which talks to a local `llama-server` process and local files. No account is required and the application does not require a cloud API key.

### Features
- Local chat with configurable GGUF models
- Conversation history in SQLite
- PDF/TXT/MD/DOCX document import and local retrieval
- Coding assistant mode
- Local utility tools: calculator, JSON formatter, text statistics
- Image understanding through a configurable local multimodal model endpoint
- Optional local image generation through ComfyUI
- Day/Night theme
- PWA installable UI
- No login

## Architecture

```text
Browser / PWA
     |
     | HTTP localhost
     v
SNS AI FastAPI
  |       |        |
  |       |        +--> SQLite (chat + document index)
  |       +-----------> local document parsers
  +-------------------> llama-server (GGUF, CPU/GPU)
                           |
                           +--> optional multimodal GGUF

Optional image generation:
SNS AI -> ComfyUI localhost -> local diffusion model
```

`llama.cpp` is used as the inference runtime because it supports quantized GGUF models, CPU inference, Apple Metal, AMD HIP/Vulkan and Android builds. See the upstream documentation linked in `docs/PLATFORM.md`.

## Quick start — Windows 11

### 1. Install Python 3.11+

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Get llama.cpp

Download/build the `llama-server` binary from the official llama.cpp project and place it at:

```text
runtime/llama-server.exe
```

Or put it on PATH.

### 3. Add a GGUF model

Put a small instruct model in:

```text
models/main.gguf
```

For an 8 GB RAM Ryzen 3 laptop, start with a small 0.5B–3B Q4/Q5 GGUF model. Larger models may work with heavy swapping but will be slow.

### 4. Start SNS AI

```powershell
python server.py
```

Open http://127.0.0.1:8787

The server will start `llama-server` automatically if `models/main.gguf` and a llama-server binary are present.

### Manual llama-server mode

You can also start llama-server yourself:

```powershell
runtime\llama-server.exe -m models\main.gguf --host 127.0.0.1 --port 8080 -c 4096
```

Then set `SNS_AI_LLM_URL=http://127.0.0.1:8080` before starting SNS AI.

## macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python server.py
```

Place the platform's `llama-server` binary in `runtime/llama-server` or on PATH.

## Android

SNS AI is designed as a web application/PWA. There are two supported approaches:

1. Run the backend on another local machine and open the PWA from the Android device over the LAN.
2. Advanced/offline: run llama.cpp locally through Termux or build an Android native binding, then point a local web shell at it.

The repository includes `docs/ANDROID.md` with the Android limitations and a path for building a native Android wrapper. A normal Android browser cannot arbitrarily spawn a native `llama-server` process, so “install PWA and everything works completely offline on Android” is not equivalent to desktop deployment.

## Environment variables

See `.env.example`.

Important values:
- `SNS_AI_LLM_URL` default `http://127.0.0.1:8080`
- `SNS_AI_MODEL` default `models/main.gguf`
- `SNS_AI_PORT` default `8787`
- `SNS_AI_CONTEXT` default `4096`
- `SNS_AI_AUTO_START` default `1`
- `SNS_AI_COMFY_URL` optional ComfyUI URL

## Security

SNS AI binds to `127.0.0.1` by default. Do not expose it to the public internet without adding authentication and TLS. Tool execution is deliberately limited to safe deterministic local utilities in this starter release.

## License

MIT for SNS AI source code. Third-party model weights and runtimes retain their own licenses.
