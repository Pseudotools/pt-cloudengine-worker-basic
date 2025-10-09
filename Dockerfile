# ─────────────────────────────────────────────
# 1. Base image: RunPod ComfyUI worker
# Reference: https://github.com/runpod-workers/worker-comfyui
# ─────────────────────────────────────────────
FROM runpod/worker-comfyui:0.3.4-base

# ─────────────────────────────────────────────
# 2. Install dependencies
# ─────────────────────────────────────────────
RUN pip install --no-cache-dir huggingface_hub gitpython

# ─────────────────────────────────────────────
# 3. Download core models from Hugging Face
# Reference: https://huggingface.co/pseudotools/pseudocomfy-models
# ─────────────────────────────────────────────
RUN mkdir -p /app/models/checkpoints /app/models/controlnet /app/models/ipadapter /app/models/clip_vision

RUN huggingface-cli download pseudotools/pseudocomfy-models checkpoints/sd_xl_base_1.0.safetensors --local-dir /app/models/checkpoints
RUN huggingface-cli download pseudotools/pseudocomfy-models checkpoints/sd_xl_refiner_1.0.safetensors --local-dir /app/models/checkpoints
RUN huggingface-cli download pseudotools/pseudocomfy-models checkpoints/Juggernaut_X_RunDiffusion_Hyper.safetensors --local-dir /app/models/checkpoints
RUN huggingface-cli download pseudotools/pseudocomfy-models checkpoints/realvisxlV50_v50LightningBakedvae.safetensors --local-dir /app/models/checkpoints
RUN huggingface-cli download pseudotools/pseudocomfy-models controlnet/control-lora-depth-rank128.safetensors --local-dir /app/models/controlnet
RUN huggingface-cli download pseudotools/pseudocomfy-models ipadapter/ip-adapter-plus_sdxl_vit-h.safetensors --local-dir /app/models/ipadapter
RUN huggingface-cli download pseudotools/pseudocomfy-models clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors --local-dir /app/models/clip_vision

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

WORKDIR /app
