"""Start the UniVerse Creator GPU runtime and print the Cloudflare quick-tunnel URL."""
import os, re, sys, time, secrets, subprocess, urllib.request
from pathlib import Path

REPO = Path("/content/universe-creator")
COMFY = Path("/content/ComfyUI")
DRIVE = Path("/content/drive/MyDrive/UniVerseCreator")
LOGS = DRIVE / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

if not (Path("/content/drive/MyDrive")).exists():
    raise SystemExit("Google Drive não está montado. Monte o Drive no Colab antes de iniciar.")

token_file = DRIVE / ".uvc_api_token"
if token_file.exists():
    token = token_file.read_text().strip()
else:
    token = secrets.token_urlsafe(36)
    token_file.write_text(token)
    try:
        token_file.chmod(0o600)
    except Exception:
        pass

env = os.environ.copy()
env["UVC_API_TOKEN"] = token
env.setdefault("COMFYUI_CHECKPOINT", "v1-5-pruned-emaonly-fp16.safetensors")
env.setdefault("COMFYUI_SD15_CHECKPOINT", "v1-5-pruned-emaonly-fp16.safetensors")
env.setdefault("COMFYUI_CONTROLNET", "control_v11p_sd15_openpose.pth")
env.setdefault("COMFYUI_MOTION_MODULE", "v3_sd15_mm.ckpt")

required = [
    COMFY / "main.py",
    COMFY / "models/checkpoints/v1-5-pruned-emaonly-fp16.safetensors",
    COMFY / "models/controlnet/control_v11p_sd15_openpose.pth",
    COMFY / "models/animatediff_models/v3_sd15_mm.ckpt",
]
missing = [str(p) for p in required if not p.exists()]
if missing:
    raise SystemExit("Faltam arquivos do motor. Execute novamente colab/bootstrap.py.\n" + "\n".join(missing))

def running(url):
    try:
        with urllib.request.urlopen(url, timeout=3):
            return True
    except Exception:
        return False

if not running("http://127.0.0.1:8188/system_stats"):
    comfy_log = (LOGS / "comfyui.log").open("a")
    subprocess.Popen(
        [sys.executable, str(COMFY / "main.py"), "--listen", "127.0.0.1", "--port", "8188", "--lowvram"],
        cwd=str(COMFY), env=env, stdout=comfy_log, stderr=subprocess.STDOUT,
        start_new_session=True
    )

for _ in range(180):
    if running("http://127.0.0.1:8188/system_stats"):
        break
    time.sleep(2)
else:
    raise SystemExit("ComfyUI não iniciou. Consulte /content/drive/MyDrive/UniVerseCreator/logs/comfyui.log")

if not running("http://127.0.0.1:8000/health"):
    api_log = (LOGS / "api.log").open("a")
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "uvc_engine:app", "--app-dir", str(REPO / "colab"),
         "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(REPO), env=env, stdout=api_log, stderr=subprocess.STDOUT,
        start_new_session=True
    )

for _ in range(60):
    if running("http://127.0.0.1:8000/health"):
        break
    time.sleep(2)
else:
    raise SystemExit("API não iniciou. Consulte /content/drive/MyDrive/UniVerseCreator/logs/api.log")

cloudflared = Path("/usr/local/bin/cloudflared")
if not cloudflared.exists():
    subprocess.run(["wget", "-q", "-O", str(cloudflared),
                    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"],
                   check=True)
    cloudflared.chmod(0o755)

tunnel_log_path = LOGS / "cloudflared.log"
tunnel_log = tunnel_log_path.open("a")
subprocess.Popen(
    [str(cloudflared), "tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:8000"],
    stdout=tunnel_log, stderr=subprocess.STDOUT, start_new_session=True
)

url = None
for _ in range(90):
    try:
        log = tunnel_log_path.read_text(errors="ignore")
        matches = re.findall(r"https://[a-z0-9-]+\\.trycloudflare\\.com", log)
        if matches:
            url = matches[-1]
            break
    except Exception:
        pass
    time.sleep(2)

if not url:
    raise SystemExit("O túnel não forneceu URL. Consulte logs/cloudflared.log no Google Drive.")

print("\\n=== UNIVERSE CREATOR GPU RUNTIME ===")
print("API:", url)
print("HEALTH:", url + "/health")
print("TOKEN:", token)
print("\\nConfigure no Worker Cloudflare:")
print("COLAB_MODULE1_URL = " + url)
print("COLAB_MODULE2_URL = " + url)
print("COLAB_API_TOKEN = o valor exibido em TOKEN")
print("\\nMantenha esta sessão do Colab ativa. A URL muda quando o túnel reinicia.")
