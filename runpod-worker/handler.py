"""
RunPod Serverless worker — Qwen-Image-2512 + `lol_keyart` LoRA → background PNG.

Built on the ai-toolkit image (known-good Qwen-Image environment). The model is
loaded LAZILY on the first request (then cached), wrapped in try/except, so a
load error returns a clean {"error": ...} in the RESPONSE instead of crash-
looping the worker — which makes debugging vastly easier.

Request  (POST /run or /runsync):
    { "input": { "prompt": str, "negative_prompt": str?, "seed": int?,
                 "width": int=1024, "height": int=1024,
                 "steps": int=30, "guidance": float=4.0 } }
Response:
    { "image_base64": "<png b64>", "seed": int|null, "width": int, "height": int }
  or { "error": "...", "trace": "..." }
"""

import base64
import io
import os
import traceback

import runpod

MODEL_DIR = os.environ.get("MODEL_DIR", "/runpod-volume/qwen-image-2512")
LORA_PATH = os.environ.get("LORA_PATH", "/runpod-volume/loras/lol_keyart.safetensors")

_pipe = None  # cached across requests on a warm worker


def _load_pipe():
    global _pipe
    if _pipe is not None:
        return _pipe
    import torch
    from diffusers import DiffusionPipeline

    print(f"[worker] loading base model: {MODEL_DIR}", flush=True)
    pipe = DiffusionPipeline.from_pretrained(MODEL_DIR, torch_dtype=torch.bfloat16)
    if os.path.exists(LORA_PATH):
        print(f"[worker] loading LoRA: {LORA_PATH}", flush=True)
        pipe.load_lora_weights(LORA_PATH)
    else:
        print(f"[worker] WARNING: LoRA not found at {LORA_PATH} - base model only", flush=True)
    pipe.to("cuda")
    print("[worker] ready.", flush=True)
    _pipe = pipe
    return _pipe


def handler(job):
    try:
        import torch

        pipe = _load_pipe()

        inp = job.get("input") or {}
        prompt = inp.get("prompt")
        if not prompt:
            return {"error": "missing required field 'input.prompt'"}

        negative = inp.get("negative_prompt") or None
        width = int(inp.get("width", 1024))
        height = int(inp.get("height", 1024))
        steps = int(inp.get("steps", 30))
        guidance = float(inp.get("guidance", 4.0))
        seed = inp.get("seed")
        generator = (
            torch.Generator(device="cuda").manual_seed(int(seed)) if seed is not None else None
        )

        kwargs = dict(
            prompt=prompt,
            negative_prompt=negative,
            width=width,
            height=height,
            num_inference_steps=steps,
            generator=generator,
        )
        # Qwen-Image uses `true_cfg_scale`; fall back to `guidance_scale` if needed.
        try:
            image = pipe(true_cfg_scale=guidance, **kwargs).images[0]
        except TypeError:
            image = pipe(guidance_scale=guidance, **kwargs).images[0]

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return {
            "image_base64": base64.b64encode(buf.getvalue()).decode("utf-8"),
            "seed": seed,
            "width": width,
            "height": height,
        }
    except Exception as e:  # noqa: BLE001 — surface the error in the response, don't crash
        return {"error": str(e), "trace": traceback.format_exc()}


runpod.serverless.start({"handler": handler})
