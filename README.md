# pt-cloudengine-worker-basic

Custom RunPod Serverless worker for [ComfyUI](https://github.com/comfyanonymous/ComfyUI), maintained by [Pseudotools](https://github.com/pseudotools).

## What this repo is

This is the **worker/deployment** repo. RunPod builds a Docker image from its `Dockerfile` and runs serverless workers from that image.

The image includes:

- A baseline ComfyUI runtime (`runpod/worker-comfyui:5.5.0-base`)
- Core SDXL models baked in at build time
- [Pseudocomfy](https://github.com/Pseudotools/Pseudocomfy) custom nodes, **pinned to an exact Git commit**
- Optional network-volume models at `/runpod-volume/models`

**Important:** Pseudocomfy is a *separate* GitHub repo. Updating Pseudocomfy on GitHub does **not** update running workers by itself. Workers only get new Pseudocomfy code when this worker image is rebuilt with a new pinned commit.

## How deployment works (mental model)

```text
This repo (Dockerfile)  ──push to main──►  RunPod builds a new Docker image
                                              │
Pseudocomfy repo        ──cloned once──►      │  (at image build time, at the pinned SHA)
                                              ▼
                                         Workers run from that frozen image
```

- Pseudocomfy is cloned **during the Docker build**, not when a worker starts.
- Changing Pseudocomfy `main` alone does nothing to production until you change the SHA in *this* Dockerfile and push.
- On this endpoint, a **push to `main`** typically starts a new RunPod build (releases are not required).

### RunPod Builds console

Watch builds / logs / status here (replace `[ENDPOINTID]` with your endpoint ID):

https://console.runpod.io/serverless/user/endpoint/[ENDPOINTID]?tab=builds

Statuses go through Pending → Building → Uploading → Testing → Completed (or Failed). Open the failed build’s log if something breaks.

---

## Updating Pseudocomfy on the worker

Do this whenever you want production workers to use a newer Pseudocomfy version.

### What a SHA is

A **SHA** (also called a commit hash) is Git’s unique ID for one exact snapshot of a repository — a long string of hex characters, e.g.:

```text
b265d767563708fcb6c5ca4cc438d00297367ea7
```

Pinning that SHA means the image always gets *that* Pseudocomfy revision, not “whatever `main` happens to be today.” Changing the SHA also forces Docker to rebuild that layer instead of reusing a stale cached clone.

### Where to find the latest Pseudocomfy SHA

1. Open [Pseudotools/Pseudocomfy](https://github.com/Pseudotools/Pseudocomfy).
2. Make sure you’re on the branch you want (usually `main`).
3. Click the latest commit on that branch (commit message / timestamp).
4. On the commit page, click the **copy** icon next to the full commit hash (or expand the short hash). You need the **full** SHA, not just the first 7 characters.

Shortcuts:

- Commits list: https://github.com/Pseudotools/Pseudocomfy/commits/main  
- Or from a terminal: `git ls-remote https://github.com/Pseudotools/Pseudocomfy.git HEAD`

### Step-by-step

1. **Get the Pseudocomfy SHA** you want to deploy (see above).
2. **Edit this repo’s `Dockerfile`.** Find:

   ```dockerfile
   ARG PSEUDOCOMFY_COMMIT=...
   ```

   Replace the value with the full new SHA.
3. **Optional:** bump `LABEL version="..."` in the Dockerfile (informational only).
4. **Commit and push** to `main` on this worker repo.
5. **Open the RunPod Builds tab** and confirm a new build starts:

   https://console.runpod.io/serverless/user/endpoint/[ENDPOINTID]?tab=builds

6. **In the build log**, confirm checkout succeeded. You should see something like:

   ```text
   HEAD is now at b265d76 ...
   b265d767563708fcb6c5ca4cc438d00297367ea7
   ```

   The printed SHA should match what you put in the Dockerfile. The same value is also written into the image at `/app/PSEUDOCOMFY_COMMIT`.
7. Wait for status **Completed**.
8. **Send a test job** that exercises the updated custom nodes.

If the build fails, read the log near `ERROR` / `tee:` / `pip install` — common issues are a bad SHA, missing `/app` paths, or Pseudocomfy dependency install failures.

### What not to do

- Do **not** add a runtime `git pull` of Pseudocomfy on worker start. That makes workers non-reproducible and harder to roll back.
- Do **not** expect a Pseudocomfy-only push to update this endpoint. Always update `PSEUDOCOMFY_COMMIT` here and rebuild.

---

## Execution Metadata (Location + Hardware) – Design Notes

Goal: return machine location and hardware information alongside job results to support energy-usage analysis.

### What we tried

- Considered directly modifying upstream worker return path (e.g., `worker-comfyui/handler.py` near the final result) — fragile because upstream can change; we do not control the base image internals. Reference: [runpod-workers/worker-comfyui handler.py L792](https://github.com/runpod-workers/worker-comfyui/blob/main/handler.py#L792).
- Attempted to replace the base image startup and run our own serverless handler. Result: images disappeared because the base image’s orchestration (ComfyUI execution, image upload) is handled by its own startup and handler system (`/start.sh`). Overriding that bypassed the image-generation/upload flow.

### Key learnings

- The base image’s startup (`/start.sh`) drives ComfyUI execution and the result packaging (including S3 upload). Replacing it with a standalone serverless start means the ComfyUI pipeline never runs, so no `images` are returned.
- A robust approach is to keep the upstream handler in place and only augment its final response.
- Avoid depending on environment variables for location; use a lightweight IP lookup and local GPU/system introspection instead.

### Robust approach (recommended)

1) Keep the base handler unchanged; add a small wrapper that imports the base handler and merges metadata into the response.

2) Collect metadata:
   - Geolocation: `https://ifconfig.co/json` (no key, fast). Cache the result once per pod to avoid repeated calls.
   - GPU: `pynvml` (NVIDIA Management Library) to capture name, power (W), utilization, memory, temperature.
   - System: `psutil` for CPU model/cores and total RAM.

3) Inject metadata as a top-level `execution_metadata` under `result["output"]`, without changing the `images` array structure.

4) Graceful fallbacks: if any probe fails, include partial data; do not fail the job.

### Example wrapper (illustrative)

```python
# /app/handler.py (our file copied into the image)
import sys
import requests, psutil, pynvml

def _get_geo_cached(_cache={}):
    if "geo" in _cache:
        return _cache["geo"]
    try:
        r = requests.get("https://ifconfig.co/json", timeout=5)
        r.raise_for_status()
        data = r.json()
        _cache["geo"] = {
            "ip": data.get("ip"),
            "city": data.get("city"),
            "region": data.get("region"),
            "country": data.get("country"),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
        }
    except Exception:
        _cache["geo"] = None
    return _cache["geo"]

def _gpu_info():
    try:
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(h)
        mem = pynvml.nvmlDeviceGetMemoryInfo(h)
        return {
            "name": pynvml.nvmlDeviceGetName(h).decode("utf-8"),
            "power_draw_watts": pynvml.nvmlDeviceGetPowerUsage(h) / 1000.0,
            "utilization_percent": util.gpu,
            "memory_used_mb": mem.used // (1024 * 1024),
            "memory_total_mb": mem.total // (1024 * 1024),
            "temperature_celsius": pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU),
        }
    except Exception:
        return None

def _system_info():
    cpu_model = "Unknown"
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.startswith("model name"):
                    cpu_model = line.split(":", 1)[1].strip()
                    break
    except Exception:
        pass
    return {
        "cpu": {"model": cpu_model, "cores": psutil.cpu_count(logical=False) or 0},
        "memory_total_gb": (psutil.virtual_memory().total // (1024 * 1024 * 1024)),
    }

def _collect_metadata():
    return {
        "location": _get_geo_cached(),
        "hardware": {"gpu": _gpu_info(), **_system_info()},
    }

def handler(job):
    # Import base handler from the image and call it
    sys.path.append("/app")
    from rp_handler import handler as base_handler
    result = base_handler(job)

    # Attach metadata without changing images structure
    meta = _collect_metadata()
    if isinstance(result, dict):
        if isinstance(result.get("output"), dict):
            result["output"]["execution_metadata"] = meta
        else:
            result["execution_metadata"] = meta
    else:
        result = {"output": result, "execution_metadata": meta}
    return result
```

Notes:
- Do not replace the base startup (`/start.sh`). Let the image orchestrate ComfyUI and uploads; only augment the final response.
- The snippet is illustrative; integrate and test inside your image build context.

### API choice

- Geolocation via `https://ifconfig.co/json` was selected for simplicity and reliability (no CAPTCHA, fast JSON endpoint).

---

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
| `BUCKET_ENDPOINT_URL` | `https://my-bucket.s3.us-east-1.amazonaws.com` | Full endpoint URL of your S3 bucket for direct image uploads. If set, images will be uploaded to S3 instead of returned as base64. | ❌       |
| `BUCKET_ACCESS_KEY_ID` | `AKIAIOSFODNN7EXAMPLE` | AWS access key ID for S3 upload permissions. Required if BUCKET_ENDPOINT_URL is set. *(Note: The dispatcher refers to this as `AWS_ACCESS_KEY_ID`)* | ✅       |
| `BUCKET_SECRET_ACCESS_KEY` | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` | AWS secret access key for S3 upload permissions. Required if BUCKET_ENDPOINT_URL is set. *(Note: The dispatcher refers to this as `AWS_SECRET_ACCESS_KEY`)* | ✅       |

🟡 **Notes:**

* `COMFYUI_AUTH_TOKEN` is **injected at runtime** from the RunPod environment.
* This token is **not** used by ComfyUI itself; it is enforced by the **RunPod worker layer** that wraps ComfyUI.
* The token prevents unauthorized access to your endpoint — only clients that include the correct bearer token can submit jobs.
* Keep this secret private and **never commit it** to GitHub or Dockerfiles.

📘 Reference: [RunPod Environment Variables](https://docs.runpod.io/serverless/workers/environment-variables)

---

### 🧱 4. Build and Deploy

Click **Deploy Worker** for the first build. After that, pushes to `main` typically start a new build automatically.

RunPod will:

1. Clone this repository.
2. Build the Docker image from the Dockerfile (including the pinned Pseudocomfy SHA).
3. Download core models from [Hugging Face](https://huggingface.co/pseudotools/pseudocomfy-models).
4. Clone Pseudocomfy at the pinned commit and install its requirements.
5. Register / update the worker image for the endpoint.

Build time is often 20–30+ minutes (large models). Monitor progress in the endpoint **Builds** tab:

https://console.runpod.io/serverless/user/endpoint/[ENDPOINTID]?tab=builds

✅ **Build succeeds when:**

* Model downloads complete without errors.
* Custom nodes install successfully.
* The log shows the expected Pseudocomfy SHA (and `/app/PSEUDOCOMFY_COMMIT` was written).
* Status reaches **Completed**.
* The worker logs show it’s “ready” or listening for RunPod jobs.

---

### ⚙️ **Configuration**

This document outlines the environment variables available for configuring the worker-comfyui.

#### General Configuration

| Environment Variable | Description | Default |
| -------------------- | ----------- | ------- |
| `REFRESH_WORKER` | When true, the worker pod will stop after each completed job to ensure a clean state for the next job. See the RunPod documentation for details. | `false` |
| `SERVE_API_LOCALLY` | When true, enables a local HTTP server simulating the RunPod environment for development and testing. See the Development Guide for more details. | `false` |
| `COMFY_ORG_API_KEY` | Comfy.org API key to enable ComfyUI API Nodes. If set, it is sent with each workflow; clients can override per request via input.api_key_comfy_org. | – |

#### Logging Configuration

| Environment Variable | Description | Default |
| -------------------- | ----------- | ------- |
| `COMFY_LOG_LEVEL` | Controls ComfyUI's internal logging verbosity. Options: DEBUG, INFO, WARNING, ERROR, CRITICAL. Use DEBUG for troubleshooting, INFO for production. | `DEBUG` |

#### Debugging Configuration

| Environment Variable | Description | Default |
| -------------------- | ----------- | ------- |
| `WEBSOCKET_RECONNECT_ATTEMPTS` | Number of websocket reconnection attempts when connection drops during job execution. | `5` |
| `WEBSOCKET_RECONNECT_DELAY_S` | Delay in seconds between websocket reconnection attempts. | `3` |
| `WEBSOCKET_TRACE` | Enable low-level websocket frame tracing for protocol debugging. Set to true only when diagnosing connection issues. | `false` |

> [!TIP]
> For troubleshooting: Set `COMFY_LOG_LEVEL=DEBUG` to get detailed logs when ComfyUI crashes or behaves unexpectedly. This helps identify the exact point of failure in your workflows.

#### AWS S3 Upload Configuration

Configure these variables only if you want the worker to upload generated images directly to an AWS S3 bucket. If these are not set, images will be returned as base64-encoded strings in the API response.

**Prerequisites:**
- An AWS S3 bucket in your desired region.
- An AWS IAM user with programmatic access (Access Key ID and Secret Access Key).
- Permissions attached to the IAM user allowing `s3:PutObject` (and potentially `s3:PutObjectAcl` if you need specific ACLs) on the target bucket.

| Environment Variable | Description | Example |
| -------------------- | ----------- | ------- |
| `BUCKET_ENDPOINT_URL` | The full endpoint URL of your S3 bucket. Must be set to enable S3 upload. | `https://<your-bucket-name>.s3.<aws-region>.amazonaws.com` |
| `BUCKET_ACCESS_KEY_ID` | Your AWS access key ID associated with the IAM user that has write permissions to the bucket. Required if BUCKET_ENDPOINT_URL is set. | `AKIAIOSFODNN7EXAMPLE` |
| `BUCKET_SECRET_ACCESS_KEY` | Your AWS secret access key associated with the IAM user. Required if BUCKET_ENDPOINT_URL is set. | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |

> **Note:** Upload uses the runpod Python library helper `rp_upload.upload_image`, which handles creating a unique path within the bucket based on the job_id.

**Example S3 Response**

If the S3 environment variables (`BUCKET_ENDPOINT_URL`, `BUCKET_ACCESS_KEY_ID`, `BUCKET_SECRET_ACCESS_KEY`) are correctly configured, a successful job response will look similar to this:

```json
{
  "id": "sync-uuid-string",
  "status": "COMPLETED",
  "output": {
    "images": [
      {
        "filename": "ComfyUI_00001_.png",
        "type": "s3_url",
        "data": "https://your-bucket-name.s3.your-region.amazonaws.com/sync-uuid-string/ComfyUI_00001_.png"
      }
      // Additional images generated by the workflow would appear here
    ]
    // The "errors" key might be present here if non-fatal issues occurred
  },
  "delayTime": 123,
  "executionTime": 4567
}
```

The `data` field contains the presigned URL to the uploaded image file in your S3 bucket. The path usually includes the job ID.

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
- Custom nodes: `/comfyui/custom_nodes/Pseudocomfy/` (cloned during build)

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

* **Updating Pseudocomfy:** Edit `PSEUDOCOMFY_COMMIT` in the Dockerfile, push to `main`, then watch Builds. Full steps are at the top of this README.
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

## ⚙️ **Bare-Bones Setup Guide**

This is the *minimal "how-to"* for deploying a Pseudotools-style ComfyUI worker on RunPod.

### 1. Create a GitHub Repository

1. Create a new repo, e.g. `pt-cloudengine-worker-basic`.
2. Add:
    - `Dockerfile`
    - `scripts/setup_models.sh`
    - `.gitignore`
    - `README.md`

### 2. Dockerfile Overview

The Dockerfile builds a ComfyUI worker that:
- Uses the official RunPod ComfyUI base image
- Installs git and Python dependencies (huggingface_hub, gitpython)
- Downloads 7 core models from Hugging Face to `/comfyui/models`
- Clones Pseudocomfy at a **pinned commit SHA** (`ARG PSEUDOCOMFY_COMMIT=...`) into `/comfyui/custom_nodes/Pseudocomfy`
- Sets up dynamic model path configuration via startup script
- Configures ComfyUI to find both baked-in and network-mounted models

### 3. Deploy on RunPod

1. Go to **RunPod Console → Serverless → New Endpoint**
2. Fill out:
    - **Repository URL** → your GitHub repo
    - **Dockerfile Path** → `Dockerfile`
    - **Container Start Command** → leave blank (ENTRYPOINT handles it)
    - **Expose HTTP Ports** → leave blank (serverless workers don't expose ports)

### 4. Add Environment Variables

| Variable | Sample Value | Purpose |
| --- | --- | --- |
| `COMFYUI_AUTH_TOKEN` | `<SERVERLESS_BEARER_TOKEN>` | API token for client requests |
| `NETWORK_VOLUME_PATH` | `/runpod-volume` | Optional path for network-mounted storage |
| `LOG_LEVEL` | `info` | Logging level |
| `BUCKET_ENDPOINT_URL` | `https://my-bucket.s3.us-east-1.amazonaws.com` | S3 endpoint for image uploads |
| `BUCKET_ACCESS_KEY_ID` | `<your_aws_access_key_id>` | AWS access key for S3 |
| `BUCKET_SECRET_ACCESS_KEY` | `<your_aws_secret_access_key>` | AWS secret key for S3 |

📘 **Tip:** Mark sensitive ones as secrets (click the 🔑 icon in RunPod).

### 5. Success Criteria

✅ Logs show:

```
🔧 Configuring ComfyUI model paths...
🧩 Model paths available at runtime:
/comfyui/models/checkpoints/sd_xl_base_1.0.safetensors
/comfyui/models/checkpoints/sd_xl_refiner_1.0.safetensors
/comfyui/models/checkpoints/Juggernaut_X_RunDiffusion_Hyper.safetensors
/comfyui/models/checkpoints/realvisxlV50_v50LightningBakedvae.safetensors
/comfyui/models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors
/comfyui/models/controlnet/control-lora-depth-rank128.safetensors
/comfyui/models/ipadapter/ip-adapter-plus_sdxl_vit-h.safetensors
```

✅ Worker status shows "Ready" and is listening for jobs.

---

### 📚 References

* [RunPod Serverless Workers](https://docs.runpod.io/serverless/workers/)
* [RunPod GitHub Integration](https://docs.runpod.io/serverless/workers/github-integration)
* [RunPod API Reference](https://docs.runpod.io/reference)
* [ComfyUI Repository](https://github.com/comfyanonymous/ComfyUI)
* [Pseudotools Custom Nodes](https://github.com/Pseudotools/Pseudocomfy)
* [Pseudotools Model Repository](https://huggingface.co/pseudotools/pseudocomfy-models)

