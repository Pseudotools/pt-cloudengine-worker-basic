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
RUN mkdir -p /comfyui/models/checkpoints /comfyui/models/controlnet /comfyui/models/ipadapter /comfyui/models/clip_vision

RUN huggingface-cli download pseudotools/pseudocomfy-models \
    checkpoints/sd_xl_base_1.0.safetensors \
    checkpoints/sd_xl_refiner_1.0.safetensors \
    controlnet/control-lora-depth-rank128.safetensors \
    ipadapter/ip-adapter-plus_sdxl_vit-h.safetensors \
    clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors \
    --local-dir /comfyui/models --local-dir-use-symlinks False

# ─────────────────────────────────────────────
# 4. Clone Pseudotools custom nodes
# Reference: https://github.com/Pseudotools/Pseudocomfy
# ─────────────────────────────────────────────
RUN git clone https://github.com/Pseudotools/Pseudocomfy /comfyui/custom_nodes/Pseudocomfy
WORKDIR /comfyui/custom_nodes/Pseudocomfy
RUN pip install --no-cache-dir -r requirements.txt
WORKDIR /app

# ─────────────────────────────────────────────
# 5. Download extension models from Hugging Face
# Reference: https://huggingface.co/pseudotools/pseudocomfy-models
# ─────────────────────────────────────────────
RUN huggingface-cli download pseudotools/pseudocomfy-models \
    checkpoints/Juggernaut_X_RunDiffusion_Hyper.safetensors \
    checkpoints/realvisxlV50_v50LightningBakedvae.safetensors \
    --local-dir /comfyui/models --local-dir-use-symlinks False

# ─────────────────────────────────────────────
# 6. Environment variables
# ─────────────────────────────────────────────
ENV HF_HUB_DISABLE_SYMLINKS_WARNING=1

# ─────────────────────────────────────────────
# Diagnostic: verify models and paths
# ─────────────────────────────────────────────
RUN echo "=== MODEL DIRECTORY STRUCTURE ===" && \
    ls -Rlh /comfyui/models || true && \
    echo "=== CUSTOM NODES DIRECTORY STRUCTURE ===" && \
    ls -Rlh /comfyui/custom_nodes || true && \
    echo "=== EXTRA MODEL PATHS CONFIG ===" && \
    cat /comfyui/extra_model_paths.yaml || true

# ─────────────────────────────────────────────
# 7. Metadata labels
# ─────────────────────────────────────────────
LABEL maintainer="pseudotools"
LABEL description="Pseudotools ComfyUI worker with baked required custom nodes and commonly-used models"
LABEL version="0.1.0"

# ─────────────────────────────────────────────
# 8. Runtime setup and entrypoint
# ─────────────────────────────────────────────
COPY scripts/setup_models.sh /app/setup_models.sh
RUN chmod +x /app/setup_models.sh

# Set the entrypoint to dynamically configure model paths
ENTRYPOINT ["/app/setup_models.sh"]
