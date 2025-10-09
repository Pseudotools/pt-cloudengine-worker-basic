# pt-cloudengine-worker-comfyui-basic

Custom RunPod worker for [ComfyUI](https://github.com/comfyanonymous/ComfyUI)  
Maintained by [Pseudotools](https://github.com/pseudotools)

## Overview
This worker provides a baseline ComfyUI runtime with:
- Core SDXL models baked into the image
- Automatically cloned [Pseudotools "Pseudocomfy" Custom Nodes](https://github.com/Pseudotools/Pseudocomfy)
- Configurable persistent storage at `/runpod-volume/models` for additional models

## Model Path Configuration

This worker automatically configures ComfyUI to recognize both baked-in and shared models.

* Baked-in models live in `/comfyui/models` (downloaded during build).
* Optional shared models can be mounted from a RunPod **network volume** at `/runpod-volume/models`.
* On startup, the worker updates `/comfyui/extra_model_paths.yaml` to include all available paths.

Example log output:

```
🔧 Configuring ComfyUI model paths...
  • Baked-in models:    /comfyui/models
  • Network volume path: /runpod-volume/models
✅ Found network models at /runpod-volume/models
  + Adding /runpod-volume/models/checkpoints to extra_model_paths.yaml
🧩 Final model paths written to /comfyui/extra_model_paths.yaml
```

If no network volume is mounted, the worker continues using the baked-in models only.

## References
- [RunPod Worker Documentation](https://docs.runpod.io/serverless/workers/)
- [RunPod ComfyUI Worker Repo](https://github.com/runpod-workers/worker-comfyui)
- [GitHub Integration Setup](https://docs.runpod.io/serverless/workers/github-integration)
- [Hugging Face Model Repo](https://huggingface.co/pseudotools/pseudocomfy-models)



## 🚀 Deployment on RunPod

This repository defines a **custom RunPod Serverless Worker** for [ComfyUI](https://github.com/comfyanonymous/ComfyUI), configured with Pseudotools’ core models and custom nodes.
The worker runs entirely within RunPod’s serverless infrastructure and communicates through the RunPod API — no exposed ports or manual networking required.

---

### 🧩 1. Prerequisites

* A [RunPod account](https://www.runpod.io/console) with access to **Serverless → Workers**.
* A linked [GitHub account](https://docs.runpod.io/serverless/workers/github-integration).
* A [Hugging Face account](https://huggingface.co/pseudotools/pseudocomfy-models) (optional for browsing models, not required for access).

---

### ⚙️ 2. Connect the GitHub Repository

1. In the RunPod Console, go to **Serverless → Workers → Create Worker**.
2. Choose **“From GitHub Repository.”**
3. Select:

   * **Repository:** `pseudotools/pt-cloudengine-worker-basic`
   * **Branch:** `main`
   * **Dockerfile path:** `/Dockerfile` (default)
4. Leave **Container Start Command** blank — the base image defines the correct entrypoint.
5. Leave **Model (optional)** blank — models are downloaded automatically inside the image.
6. Do **not** expose any ports. This worker communicates through the RunPod job API.

📘 Reference: [RunPod GitHub Integration Guide](https://docs.runpod.io/serverless/workers/github-integration)

---

### 🔐 3. Configure Environment Variables

Under **Environment Variables**, add the following:

| Variable              | Example                    | Purpose                                                                                                                                        | Secret? |
| --------------------- | -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| `COMFYUI_AUTH_TOKEN`  | `pseudotools-secret-token` | Bearer token required to authenticate API requests to this worker. Clients must include it in the `Authorization` header when submitting jobs. *(Note: The dispatcher refers to this as `SERVERLESS_BEARER_TOKEN`)* | ✅       |
| `NETWORK_VOLUME_PATH` | `/runpod-volume`           | Optional path for network-mounted storage. Used if attached to this endpoint.                                                                  | ❌       |
| `LOG_LEVEL`           | `info`                     | Logging verbosity for the worker.                                                                                                              | ❌       |

🟡 **Notes:**

* `COMFYUI_AUTH_TOKEN` is **injected at runtime** from the RunPod environment.
* This token is **not** used by ComfyUI itself; it is enforced by the **RunPod worker layer** that wraps ComfyUI.
* The token prevents unauthorized access to your endpoint — only clients that include the correct bearer token can submit jobs.
* Keep this secret private and **never commit it** to GitHub or Dockerfiles.

📘 Reference: [RunPod Environment Variables](https://docs.runpod.io/serverless/workers/environment-variables)

---

### 🧱 4. Build and Deploy

Click **Deploy Worker**.
RunPod will automatically:

1. Clone this repository.
2. Build the Docker image using the provided Dockerfile.
3. Download core models from [Hugging Face](https://huggingface.co/pseudotools/pseudocomfy-models).
4. Clone and install [Pseudocomfy custom nodes](https://github.com/Pseudotools/Pseudocomfy).
5. Register the worker with the RunPod job system.

Build time typically takes 20–30 minutes (depending on model size).
You can monitor progress in **Build Logs**.

✅ **Build succeeds when:**

* Model downloads complete without errors.
* Custom nodes install successfully.
* The worker logs show it’s “ready” or listening for RunPod jobs.

---

### 🔐 **Authenticating API Requests**

The RunPod ComfyUI worker requires all API requests to include a valid bearer token for authentication.
This token is defined by the environment variable `COMFYUI_AUTH_TOKEN` *(Note: The dispatcher refers to this as `SERVERLESS_BEARER_TOKEN`)*.

**To set up:**

1. In your RunPod endpoint settings, add:

   ```
   COMFYUI_AUTH_TOKEN=pseudotools-secret-token
   ```
2. When sending requests to your endpoint, include:

   ```http
   Authorization: Bearer pseudotools-secret-token
   ```
3. You will see the following log entries when authenticated:

   ```
   Authenticated with Bearer token
   ```

If this header is missing or incorrect, the worker will respond with:

```json
{
  "error": "Unauthorized"
}
```

This provides lightweight security for your worker endpoint without needing a separate authentication service.

---

### 🧪 5. Test the Worker Endpoint

Once deployment completes:

1. In **RunPod → Workers**, open your worker and click **Endpoints → View Worker Endpoint**.
   You’ll get a public endpoint like:

   ```
   https://api.runpod.ai/v2/<worker-id>/run
   ```

2. Send a test request with proper authentication:

   ```bash
   curl -X POST https://api.runpod.ai/v2/<worker-id>/run \
     -H "Authorization: Bearer <COMFYUI_AUTH_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "an architectural scene with natural light"}}'
   ```
   
   *(Note: Replace `<COMFYUI_AUTH_TOKEN>` with your actual token value. The dispatcher refers to this as `SERVERLESS_BEARER_TOKEN`)*

3. The worker will respond with job metadata and begin processing.
   Jobs can be monitored via the RunPod dashboard or API.

📘 Reference: [RunPod API Reference](https://docs.runpod.io/reference)

---

### 🧠 6. Model and Node Directories

**Model paths are configured dynamically at startup:**
- Baked-in models: `/comfyui/models/` (downloaded during build)
- Network volume models: `/runpod-volume/models/` (if mounted)

**Custom nodes are automatically available:**
- Custom nodes: `/app/custom_nodes/` (cloned during build)

The startup script automatically updates ComfyUI's configuration to include all available model directories.

Optionally, you can mount a persistent volume at `/runpod-volume/models`
to add or update models without rebuilding the image.

---

### 📦 7. Verify the Deployment

After the worker starts, open the **Logs** tab in RunPod and confirm:

```
🔧 Configuring ComfyUI model paths...
  • Baked-in models:    /comfyui/models
  • Network volume path: /runpod-volume/models
✅ Downloaded model sd_xl_base_1.0.safetensors
✅ Cloned custom nodes from Pseudotools/Pseudocomfy
🧩 Final model paths written to /comfyui/extra_model_paths.yaml
Worker initialized and listening for jobs...
```

---

### 🧭 8. Integration with Pseudotools Cloud Engine

Once verified, register the new worker endpoint in your orchestration service
(`pt-cloudengine-dispatcher` or equivalent) by adding it as a ComfyUI backend:

```python
headers = {
    "Authorization": f"Bearer {COMFYUI_AUTH_TOKEN}",
    "Content-Type": "application/json"
}

requests.post(
    "https://api.runpod.ai/v2/<worker-id>/run",
    headers=headers,
    json={"input": {"workflow": "Hugo", "prompt": "sunlit atrium"}}
)
```

**Note:** Replace `{COMFYUI_AUTH_TOKEN}` with your actual bearer token value. *(The dispatcher refers to this as `SERVERLESS_BEARER_TOKEN`)*

This allows your local or cloud services to dispatch jobs directly to this worker.

---

### ✅ 9. Notes and Best Practices

* **Build limits:** RunPod GitHub builds must complete within 160 minutes and stay under 80 GB total image size.
* **Security:** Never bake secrets or tokens into the Dockerfile.
* **Variants:**
  Fork this repo for additional worker types:

  * `pt-cloudengine-worker-comfyui-xl` — extended SDXL setup
  * `pt-cloudengine-worker-comfyui-lora` — LoRA or ControlNet-heavy builds
  * `pt-cloudengine-worker-comfyui-materials` — material inference builds
* **Persistence:**
  Mount `/runpod-volume/models` or `/runpod-volume/custom_nodes` to retain files between runs.

---

### 📚 References

* [RunPod Serverless Workers](https://docs.runpod.io/serverless/workers/)
* [RunPod GitHub Integration](https://docs.runpod.io/serverless/workers/github-integration)
* [RunPod API Reference](https://docs.runpod.io/reference)
* [ComfyUI Repository](https://github.com/comfyanonymous/ComfyUI)
* [Pseudotools Custom Nodes](https://github.com/Pseudotools/Pseudocomfy)
* [Pseudotools Model Repository](https://huggingface.co/pseudotools/pseudocomfy-models)

