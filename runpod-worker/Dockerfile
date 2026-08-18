# RunPod Serverless worker for Qwen-Image-2512 + lol_keyart LoRA.
#
# Built on the ai-toolkit image on purpose: it already has a torch + diffusers
# combo that RUNS Qwen-Image-2512 (it trained this LoRA), so it avoids the
# diffusers/torch "infer_schema / flash_attn_3 custom op" import crash, and it
# loads the ai-toolkit-saved LoRA cleanly (same environment that wrote it).
# The model + LoRA still come from the attached network volume (/runpod-volume).
FROM ostris/aitoolkit:latest

WORKDIR /app

RUN python -m pip install --no-cache-dir --break-system-packages runpod

COPY handler.py .

CMD ["python", "-u", "handler.py"]
