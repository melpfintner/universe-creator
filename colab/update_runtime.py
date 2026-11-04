"""Update UniVerse Creator API code without restarting ComfyUI or cloudflared.
Run from a Colab cell after the repository has been cloned:
!python /content/universe-creator/colab/update_runtime.py
"""
import os, sys, time, signal, subprocess
from pathlib import Path

REPO = Path("/content/universe-creator")
DRIVE = Path("/content/drive/MyDrive/UniVerseCreator")
TOKEN_FILE = DRIVE / ".uvc_api_token"
LOGS = DRIVE / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

if not (REPO / ".git").exists():
    raise SystemExit("Repositório UniVerse Creator não encontrado em /content/universe-creator.")
if not TOKEN_FILE.exists():
    raise SystemExit("Token persistente não encontrado no Google Drive. Não vou gerar outro token porque isso quebraria a autenticação da Cloudflare.")

print("Atualizando os arquivos do GitHub...", flush=True)
subprocess.run(["git", "pull", "--ff-only", "origin", "main"], cwd=REPO, check=True)

token = TOKEN_FILE.read_text().strip()
if not token:
    raise SystemExit("O arquivo de token está vazio. Nenhum processo foi reiniciado.")

# Locate only the API process launched for this project. ComfyUI and cloudflared stay up.
api_pids = []
for proc in Path("/proc").iterdir():
    if not proc.name.isdigit():
        continue
    try:
        cmdline = (proc / "cmdline").read_bytes().replace(b"\x00", b" ").decode(errors="ignore")
        if "uvicorn uvc_engine:app" in cmdline and str(REPO / "colab") in cmdline:
            api_pids.append(int(proc.name))
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        continue

for pid in api_pids:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass

deadline = time.time() + 15
while time.time() < deadline:
    alive = []
    for pid in api_pids:
        if Path(f"/proc/{pid}").exists():
            alive.append(pid)
    if not alive:
        break
    time.sleep(0.5)
else:
    for pid in alive:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

env = os.environ.copy()
env["UVC_API_TOKEN"] = token
env.setdefault("COMFYUI_CHECKPOINT", "v1-5-pruned-emaonly-fp16.safetensors")
env.setdefault("COMFYUI_SD15_CHECKPOINT", "v1-5-pruned-emaonly-fp16.safetensors")
env.setdefault("COMFYUI_CONTROLNET", "control_v11p_sd15_openpose.pth")
env.setdefault("COMFYUI_MOTION_MODULE", "v3_sd15_mm.ckpt")

log = (LOGS / "api.log").open("a", encoding="utf-8")
subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "uvc_engine:app", "--app-dir", str(REPO / "colab"),
     "--host", "127.0.0.1", "--port", "8000"],
    cwd=str(REPO), env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
)

# Verify local API startup; do not touch the ComfyUI or tunnel processes.
import urllib.request
for _ in range(30):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=3) as response:
            print("API atualizada. Health HTTP:", response.status, flush=True)
            print("ComfyUI e cloudflared não foram reiniciados.", flush=True)
            raise SystemExit(0)
    except Exception:
        time.sleep(1)

raise SystemExit("A API não respondeu após a atualização. Consulte UniVerseCreator/logs/api.log no Google Drive.")
