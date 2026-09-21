# Android deployment

SNS AI's main product is a web app. There are two practical Android modes.

## Mode A — LAN/local backend
Run SNS AI on Windows/macOS/Linux. Open the service from Android over your trusted LAN. This is not “phone-only offline”; the computer remains the inference host.

## Mode B — phone-only local inference
Use the llama.cpp Android build or Termux to run a GGUF model locally. The upstream project documents both Android Studio bindings and Termux builds. A future production wrapper can package the static SNS AI web UI into a WebView and expose a localhost bridge to the native inference engine.

Recommended starting point on Android: small 0.5B–3B quantized models, short context, and conservative concurrency. Exact speed and supported acceleration depend on the phone's SoC/GPU and Android version.
