"""UniVerse Creator Colab bootstrap.
Run in a Colab cell after cloning/downloading this repository:
    %run /content/universe-creator/colab/bootstrap.py
This installs open-source runtimes and starts the API. Model weights are NOT
downloaded automatically; configure them separately in ComfyUI/models.
"""
import os, sys, subprocess, time
from pathlib import Path

def run(args, cwd=None):
    print("+", " ".join(map(str,args)), flush=True)
    subprocess.run(args, cwd=cwd, check=True)

try:
    from google.colab import drive
    drive.mount("/content/drive")
except Exception as exc:
    raise RuntimeError("Execute este script dentro do Google Colab e autorize o Google Drive.") from exc

ROOT = Path("/content/drive/MyDrive/UniVerseCreator")
ROOT.mkdir(parents=True, exist_ok=True)
REPO = Path("/content/universe-creator")
if not REPO.exists():
    raise RuntimeError("Clone o repositório em /content/universe-creator antes de executar.")
ENGINE = REPO / "colab" / "uvc_engine.py"
if not ENGINE.exists():
    raise RuntimeError("Arquivo colab/uvc_engine.py não encontrado no repositório.")

if not Path("/content/ComfyUI/main.py").exists():
    run(["git","clone","https://github.com/comfyanonymous/ComfyUI.git","/content/ComfyUI"])
run([sys.executable,"-m","pip","install","-r",str(REPO/"colab"/"requirements.txt")])
run([sys.executable,"-m","pip","install","-r","requirements.txt"],cwd="/content/ComfyUI")

custom = Path("/content/ComfyUI/custom_nodes")
custom.mkdir(parents=True,exist_ok=True)
nodes = {
 "ComfyUI-Manager":"https://github.com/ltdrdata/ComfyUI-Manager.git",
 "ComfyUI-AnimateDiff-Evolved":"https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved.git",
 "ComfyUI-VideoHelperSuite":"https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
 "comfyui_controlnet_aux":"https://github.com/Fannovel16/comfyui_controlnet_aux.git",
 "ComfyUI_IPAdapter_plus":"https://github.com/cubiq/ComfyUI_IPAdapter_plus.git",
}
for name,url in nodes.items():
    dest=custom/name
    if not dest.exists():
        run(["git","clone",url,str(dest)])
    reqfile=dest/"requirements.txt"
    if reqfile.exists():
        run([sys.executable,"-m","pip","install","-r",str(reqfile)])

kohya=Path("/content/kohya_ss")
if not (kohya/"sd-scripts"/"train_network.py").exists():
    run(["git","clone","https://github.com/bmaltais/kohya_ss.git",str(kohya)])
kohya_req=kohya/"requirements.txt"
if kohya_req.exists():
    run([sys.executable,"-m","pip","install","-r",str(kohya_req)])

for folder in ["checkpoints","controlnet","loras","vae","clip_vision","animatediff_models"]:
    (Path("/content/ComfyUI/models")/folder).mkdir(parents=True,exist_ok=True)

gpu=subprocess.run(["nvidia-smi"],capture_output=True,text=True)
if gpu.returncode != 0:
    raise RuntimeError("Nenhuma GPU NVIDIA disponível nesta sessão. No Colab, selecione Ambiente de execução > Alterar tipo de ambiente de execução > GPU.")
print(gpu.stdout[:2500])
print("\nINSTALAÇÃO BASE CONCLUÍDA.")
print("IMPORTANTE: ainda é necessário colocar pesos/modelos licenciados nas pastas de ComfyUI/models.")
print("Configure COMFYUI_CHECKPOINT, COMFYUI_CONTROLNET, COMFYUI_MOTION_MODULE e COMFYUI_SVD_CHECKPOINT.")
print("Para iniciar o ComfyUI, execute em uma célula: !python /content/ComfyUI/main.py --listen 127.0.0.1 --port 8188")
print("Em outra célula, execute: !uvicorn uvc_engine:app --app-dir /content/universe-creator/colab --host 0.0.0.0 --port 8000")
