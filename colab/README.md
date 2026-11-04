# UniVerse Creator — Colab GPU engine

This folder contains the FastAPI bridge and the Colab bootstrap for the open-source generation stack. The Cloudflare Worker remains the public API gateway; this backend is the GPU processor; Google Drive stores identities, datasets, LoRAs and generated media.

## 1. Start a Colab GPU runtime

In Colab choose Runtime → Change runtime type → T4 GPU (or another available NVIDIA GPU). Clone this repository in a Colab cell:

```bash
!git clone https://github.com/melpfintner/universe-creator.git /content/universe-creator
%run /content/universe-creator/colab/bootstrap.py
```

The bootstrap mounts Drive, installs ComfyUI, Kohya_ss, AnimateDiff-Evolved, VideoHelperSuite, ControlNet auxiliary nodes and IPAdapter Plus. It does not download model weights automatically.

## 2. Add model weights

Place model files in the matching ComfyUI directories. Use only model weights whose licenses permit your intended use.

- SDXL checkpoint: `/content/ComfyUI/models/checkpoints/`
- SD 1.5 checkpoint: `/content/ComfyUI/models/checkpoints/`
- ControlNet checkpoint: `/content/ComfyUI/models/controlnet/`
- AnimateDiff motion module: `/content/ComfyUI/models/animatediff_models/`
- IPAdapter weights: `/content/ComfyUI/models/ipadapter/`
- CLIP Vision weights: `/content/ComfyUI/models/clip_vision/`
- Stable Video Diffusion checkpoint: `/content/ComfyUI/models/checkpoints/`

Set the environment variables before starting the API:

- `COMFYUI_CHECKPOINT`: exact SDXL checkpoint filename.
- `COMFYUI_SD15_CHECKPOINT`: exact SD 1.5 checkpoint filename.
- `COMFYUI_CONTROLNET`: exact ControlNet model filename.
- `COMFYUI_MOTION_MODULE`: exact AnimateDiff motion module filename.
- `COMFYUI_SVD_CHECKPOINT`: exact SVD checkpoint filename.

A model being configured by filename does not mean the file is installed. The health endpoint should report the actual files before generation is attempted.

## 3. Start the services in separate Colab cells

Cell A:

```bash
!python /content/ComfyUI/main.py --listen 127.0.0.1 --port 8188
```

Cell B:

```bash
!uvicorn uvc_engine:app --app-dir /content/universe-creator/colab --host 0.0.0.0 --port 8000
```

Keep both cells running. The public Colab proxy URL for port 8000 must be copied from the active runtime and stored in Cloudflare as `COLAB_MODULE1_URL`, ending in `/create_identity`. The same base URL is currently used by the Worker for the additional engine routes. Do not reuse a proxy URL from an earlier runtime; Colab proxy URLs can change after a restart.

## 4. Verify the backend before using the app

Open the active public proxy URL with `/health`. Expected healthy response includes `drive: true` and `comfyui: true`. Check that the configured model flags are true before requesting the matching generation type.

## Important constraints

- A Colab free runtime is temporary, can disconnect and does not guarantee GPU availability.
- Kohya_ss LoRA training needs a suitable set of training photos, captions, GPU memory and time. Registration of an identity is not the same as training a LoRA.
- ControlNet, IPAdapter, AnimateDiff and SVD require their corresponding compatible model weights and ComfyUI nodes.
- This setup does not promise that every generation workflow is ready merely because the API responds with HTTP 200. A successful generation must return an actual image/video file.
