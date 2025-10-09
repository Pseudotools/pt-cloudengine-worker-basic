# pt-cloudengine-worker-comfyui-basic

Custom RunPod worker for [ComfyUI](https://github.com/comfyanonymous/ComfyUI)  
Maintained by [Pseudotools](https://github.com/pseudotools)

## Overview
This worker provides a baseline ComfyUI runtime with:
- Core SDXL models baked into the image
- Automatically cloned [Pseudotools "Pseudocomfy" Custom Nodes](https://github.com/Pseudotools/Pseudocomfy)
- Configurable persistent storage at `/runpod-volume/models` for additional models

## References
- [RunPod Worker Documentation](https://docs.runpod.io/serverless/workers/)
- [RunPod ComfyUI Worker Repo](https://github.com/runpod-workers/worker-comfyui)
- [GitHub Integration Setup](https://docs.runpod.io/serverless/workers/github-integration)
- [Hugging Face Model Repo](https://huggingface.co/pseudotools/pseudocomfy-models)

## Deployment Steps
1. Push this repo to GitHub.
2. In RunPod → *Serverless → Workers → Create Worker → From GitHub*.
3. Select this repo and branch (`main`).
4. Confirm build settings (context `/`).
5. Add environment variables if needed (e.g. Hugging Face token).
6. Deploy — RunPod builds and deploys automatically.
