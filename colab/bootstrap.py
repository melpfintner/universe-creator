"""UniVerse Creator Colab bootstrap.
Instala o backend sem substituir a versão de PyTorch fornecida pela GPU do Colab.
Os pesos dos modelos devem ser adicionados separadamente, respeitando suas licenças.
"""
import os, sys, subprocess, tempfile
from pathlib import Path

def run(args, cwd=None):
    print("+", " ".join(map(str,args)), flush=True)
    subprocess.run(args, cwd=cwd, check=True)

def install_requirements(path, label, cwd=None):
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
        # Kohya pins NumPy 1.x and SciPy 1.11.4, which have no compatible
        # wheels for the Colab Python 3.13 runtime. Keep Colab's working
        # NumPy/SciPy versions instead of forcing an impossible source build.
        if label == "kohya" and package == "onnx":
            print(f"REPLACE {label}: {stripped} -> onnx==1.20.1")
            lines.append("onnx==1.20.1")
            continue
        # Preserve Colab's shared Google/TensorFlow runtime dependencies.
        # The old Kohya pins downgrade these packages and break preinstalled services.
        if package in ("numpy", "scipy", "aiofiles", "protobuf"):
            print(f"SKIP {label} (use Colab-compatible version): {stripped}")
            continue
        lines.append(line)
    temp = Path("/tmp") / f"uvc-{label}-requirements.txt"
    temp.write_text("\n".join(lines))
    run([sys.executable, "-m", "pip", "install", "-r", str(temp)], cwd=cwd)

# O Drive deve ser montado em uma célula interativa do Colab antes deste script.
# Em execução por subprocess, drive.mount() falha porque não há kernel IPython associado.
if not Path("/content/drive/MyDrive").exists():
    raise RuntimeError("Google Drive não está montado. Execute em uma célula do Colab: from google.colab import drive; drive.mount('/content/drive')")
print("Google Drive já está montado.", flush=True)

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
if not (kohya/".git").exists():
    run(["git","clone","https://github.com/bmaltais/kohya_ss.git",str(kohya)])
# O sd-scripts é um submódulo do Kohya_ss. Sem inicializá-lo, o pip falha
# ao encontrar a linha "-e ./sd-scripts" no requirements.txt.
run(["git","submodule","update","--init","--recursive"], cwd=kohya)
if not (kohya/"sd-scripts"/"train_network.py").exists():
    raise RuntimeError("O submódulo sd-scripts do Kohya_ss não foi baixado corretamente.")
# Instala dependências não-PyTorch do Kohya sem substituir o torch do runtime.
install_requirements(kohya/"requirements.txt", "kohya", cwd=kohya)
# Restore versions compatible with the current Colab Google/TensorFlow stack.
run([sys.executable, "-m", "pip", "install", "--upgrade", "aiofiles>=24.1,<25", "protobuf>=6.33.5,<7"])

for folder in ["checkpoints","controlnet","loras","vae","clip_vision","ipadapter","animatediff_models"]:
    (Path("/content/ComfyUI/models")/folder).mkdir(parents=True,exist_ok=True)

# Download a practical SD 1.5 stack for the Colab T4 (16 GB VRAM).
def download_model(url, destination):
    destination = Path(destination)
    if destination.exists() and destination.stat().st_size > 100_000_000:
        print(f"MODEL OK: {destination.name}", flush=True)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    run(["wget", "-c", "--show-progress", "-O", str(destination), url])

download_model(
    "https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive/resolve/main/v1-5-pruned-emaonly-fp16.safetensors",
    "/content/ComfyUI/models/checkpoints/v1-5-pruned-emaonly-fp16.safetensors"
)
download_model(
    "https://huggingface.co/lllyasviel/ControlNet-v1-1/resolve/main/control_v11p_sd15_openpose.pth",
    "/content/ComfyUI/models/controlnet/control_v11p_sd15_openpose.pth"
)
download_model(
    "https://huggingface.co/guoyww/animatediff/resolve/main/v3_sd15_mm.ckpt",
    "/content/ComfyUI/models/animatediff_models/v3_sd15_mm.ckpt"
)

gpu=subprocess.run(["nvidia-smi"],capture_output=True,text=True)
if gpu.returncode != 0:
    raise RuntimeError("Nenhuma GPU NVIDIA disponível. Selecione Ambiente de execução > Alterar tipo > GPU.")
print(gpu.stdout[:2500])
print("\nINSTALAÇÃO BASE CONCLUÍDA.")
print("O PyTorch/CUDA existente foi preservado. Confira os avisos de dependências incompatíveis.")
print("Pesos de modelos NÃO são baixados automaticamente. Adicione apenas arquivos com licença adequada.")
print("Stack SD1.5, ControlNet OpenPose e AnimateDiff v3 baixados para o runtime T4.")
print("SVD permanece opcional: o checkpoint oficial exige aceite de licença/termos na Hugging Face.")
print("Inicie o ComfyUI em uma célula: !python /content/ComfyUI/main.py --listen 127.0.0.1 --port 8188")
print("Inicie a API em outra: !uvicorn uvc_engine:app --app-dir /content/universe-creator/colab --host 0.0.0.0 --port 8000")
