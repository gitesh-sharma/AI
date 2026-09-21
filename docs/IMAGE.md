# Image feature

SNS AI keeps image generation local by design. The starter exposes a local `/api/image/generate` bridge point but does not ship a giant diffusion checkpoint or assume a specific ComfyUI workflow.

For production image generation, run ComfyUI on the same machine with a local diffusion checkpoint, then implement the workflow payload in `server.py`. This keeps the model files outside Git and avoids cloud APIs.

Image understanding is similarly model-dependent: use a local multimodal GGUF model with a llama.cpp build that supports multimodal input, or add a local vision service behind the same adapter boundary.
