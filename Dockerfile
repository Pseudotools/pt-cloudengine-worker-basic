# ─────────────────────────────────────────────
# 1. Base image: RunPod ComfyUI worker
# Reference: https://github.com/runpod-workers/worker-comfyui
# ─────────────────────────────────────────────
FROM runpod/worker-comfyui:5.5.0-base

# ─────────────────────────────────────────────
# 2. Ensure git is available and install dependencies
# ─────────────────────────────────────────────
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir huggingface_hub gitpython

# ─────────────────────────────────────────────
# 3. Download core models from Hugging Face
# Reference: https://huggingface.co/pseudotools/pseudocomfy-models
# ─────────────────────────────────────────────
RUN mkdir -p /app/models/checkpoints /app/models/controlnet /app/models/ipadapter /app/models/clip_vision

RUN huggingface-cli download pseudotools/pseudocomfy-models \
    checkpoints/sd_xl_base_1.0.safetensors \
    checkpoints/sd_xl_refiner_1.0.safetensors \
    checkpoints/Juggernaut_X_RunDiffusion_Hyper.safetensors \
    checkpoints/realvisxlV50_v50LightningBakedvae.safetensors \
    controlnet/control-lora-depth-rank128.safetensors \
    ipadapter/ip-adapter-plus_sdxl_vit-h.safetensors \
    clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors \
    --local-dir /app/models --local-dir-use-symlinks False

# ─────────────────────────────────────────────
# 4. Clone Pseudotools custom nodes
# Reference: https://github.com/Pseudotools/Pseudocomfy
# ─────────────────────────────────────────────
RUN git clone https://github.com/Pseudotools/Pseudocomfy /app/custom_nodes
WORKDIR /app/custom_nodes
RUN pip install --no-cache-dir -r requirements.txt
WORKDIR /app

# ─────────────────────────────────────────────
# 5. Environment variables
# ─────────────────────────────────────────────
ENV MODEL_PATH=/app/models \
    CUSTOM_NODE_PATH=/app/custom_nodes \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1

# ─────────────────────────────────────────────
# 6. Metadata labels
# ─────────────────────────────────────────────
LABEL maintainer="pseudotools"
LABEL description="Pseudotools ComfyUI worker with baked required custom nodes and commonly-used models"
LABEL version="0.1.0"

WORKDIR /app
