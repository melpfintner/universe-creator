"""UniVerse Creator Colab bootstrap.
Instala o backend sem substituir a versão de PyTorch fornecida pela GPU do Colab.
Os pesos dos modelos devem ser adicionados separadamente, respeitando suas licenças.
"""
import os, sys, subprocess, tempfile
from pathlib import Path

def run(args, cwd=None):
    print("+", " ".join(map(str,args)), flush=True)
    subprocess.run(args, cwd=cwd, check=True)

def install_requirements(path, label):
    path = Path(path)
    if not path.exists():
        return
    # Preserva o PyTorch/CUDA do runtime Colab. Dependências que exigem
    # versões específicas de torch precisam ser resolvidas manualmente.
    blocked = ("torch", "torchvision", "torchaudio", "xformers", "triton")
    lines = []
    for line in path.read_text(errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "-f ", "--")):
            lines.append(line)
            continue
        package = stripped.split(";")[0].split("[")[0].split("==")[0].split(">=")[0].split("<")[0].strip().lower().replace("_","-")
        if any(package == item or package.startswith(item+"-") for item in blocked):
            print(f"SKIP {label}: {stripped}")
            continue
        lines.append(line)
    temp = Path("/tmp") / f"uvc-{label}-requirements.txt"
    temp.write_text("\n".join(lines))
    run([sys.executable, "-m", "pip", "install", "-r", str(temp)])

try:
    from google.colab import drive
    drive.mount("/content/drive")
except Exception as exc:
    raise RuntimeError("Execute este script dentro do Google Colab e autorize o Google Drive.") from exc

ROOT = Path("/content/drive/MyDrive/UniVerseCreator")
ROOT.mkdir(parents=True, exist_ok=True)
REPO = Path("/content/universe-creator")
if not (REPO / "colab" / "uvc_engine.py").exists():
    raise RuntimeError("Clone o repositório em /content/universe-creator antes de executar.")

if not Path("/content/ComfyUI/main.py").exists():
    run(["git","clone","https://github.com/comfyanonymous/ComfyUI.git","/content/ComfyUI"])

# Primeiro instala a API e dependências básicas.
install_requirements(REPO/"colab"/"requirements.txt", "api")
# Instala dependências do ComfyUI sem trocar torch/CUDA do Colab.
install_requirements("/content/ComfyUI/requirements.txt", "comfyui")

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
    install_requirements(dest/"requirements.txt", name.lower().replace("-","_"))

kohya=Path("/content/kohya_ss")
if not (kohya/"sd-scripts"/"train_network.py").exists():
    run(["git","clone","https://github.com/bmaltais/kohya_ss.git",str(kohya)])
# Instala dependências não-PyTorch do Kohya sem substituir o torch do runtime.
install_requirements(kohya/"requirements.txt", "kohya")

for folder in ["checkpoints","controlnet","loras","vae","clip_vision","ipadapter","animatediff_models"]:
    (Path("/content/ComfyUI/models")/folder).mkdir(parents=True,exist_ok=True)

gpu=subprocess.run(["nvidia-smi"],capture_output=True,text=True)
if gpu.returncode != 0:
    raise RuntimeError("Nenhuma GPU NVIDIA disponível. Selecione Ambiente de execução > Alterar tipo > GPU.")
print(gpu.stdout[:2500])
print("\nINSTALAÇÃO BASE CONCLUÍDA.")
print("O PyTorch/CUDA existente foi preservado. Confira os avisos de dependências incompatíveis.")
print("Pesos de modelos NÃO são baixados automaticamente. Adicione apenas arquivos com licença adequada.")
print("Configure COMFYUI_CHECKPOINT, COMFYUI_SD15_CHECKPOINT, COMFYUI_CONTROLNET, COMFYUI_MOTION_MODULE e COMFYUI_SVD_CHECKPOINT.")
print("Inicie o ComfyUI em uma célula: !python /content/ComfyUI/main.py --listen 127.0.0.1 --port 8188")
print("Inicie a API em outra: !uvicorn uvc_engine:app --app-dir /content/universe-creator/colab --host 0.0.0.0 --port 8000")
