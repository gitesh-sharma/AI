# Platform notes

## Windows
Best fit for the supplied Ryzen 3 3250U / 8 GB machine is CPU inference with a small quantized GGUF model. The laptop's integrated Radeon graphics may be usable through a compatible Vulkan build, but CPU mode is the baseline and is simpler.

## macOS
Apple Silicon systems can use llama.cpp's Metal backend. Intel Macs should use CPU/other supported backends. Model size should match available unified/system memory.

## Linux
CPU works everywhere supported by llama.cpp. Vulkan, CUDA, HIP and other backends depend on the installed GPU and drivers.

## Android
llama.cpp has an Android build path and a sample Android binding. A browser/PWA cannot launch a native model process by itself. For a genuinely offline Android deployment, use a native wrapper or Termux and then serve/bridge the web UI locally. Keep context and model size conservative because Android may kill memory-heavy processes.

## Offline boundary
After the model/runtime, Python dependencies and optional image models are downloaded, normal inference, chat history, document parsing and deterministic tools work without internet. Model downloads, package installation and optional external integrations require internet at setup time.
