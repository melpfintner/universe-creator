import os, io, json, time, uuid, base64, shutil, asyncio, subprocess
from pathlib import Path
from typing import Optional
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ROOT = Path("/content/drive/MyDrive/UniVerseCreator")
IDENTITIES = ROOT / "identities"
GENERATED = ROOT / "generated"
LORAS = ROOT / "loras"
for p in (IDENTITIES, GENERATED, LORAS): p.mkdir(parents=True, exist_ok=True)

COMFY = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
CHECKPOINT = os.getenv("COMFYUI_CHECKPOINT", "sd_xl_base_1.0.safetensors")
app = FastAPI(title="UniVerse Creator Engine", version="2.0")

class IdentityIn(BaseModel):
    module: Optional[str] = None
    action: Optional[str] = None
    mode: str = "influencer"
    name: str = ""
    prompt: str = Field(min_length=8, max_length=5000)
    referenceImage: Optional[str] = None
    identityId: Optional[str] = None

class ImageIn(BaseModel):
    module: Optional[int] = 2
    action: Optional[str] = "generate_image"
    prompt: str = Field(min_length=8, max_length=5000)
    identityId: Optional[str] = None
    referenceImage: Optional[str] = None
    width: int = 1024
    height: int = 1024
    steps: int = 28
    cfg: float = 6.5
    seed: Optional[int] = None
    negativePrompt: str = "blurry, low quality, deformed hands, extra fingers, watermark, text, logo"

def decode_data_url(value: str):
    if not value or "," not in value: raise HTTPException(400, "Imagem de referência inválida.")
    head, payload = value.split(",", 1)
    if not head.startswith("data:image/"): raise HTTPException(415, "A referência precisa ser uma imagem.")
    try: return base64.b64decode(payload)
    except Exception: raise HTTPException(400, "Não foi possível decodificar a referência.")

def comfy_prompt(req: ImageIn, uploaded_name=None):
    seed = req.seed if req.seed is not None else int(time.time() * 1000) % 2147483647
    workflow = {
      "1":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":CHECKPOINT}},
      "2":{"class_type":"CLIPTextEncode","inputs":{"text":req.prompt,"clip":["1",1]}},
      "3":{"class_type":"CLIPTextEncode","inputs":{"text":req.negativePrompt,"clip":["1",1]}},
      "4":{"class_type":"EmptyLatentImage","inputs":{"width":max(512,min(1536,req.width//64*64)),"height":max(512,min(1536,req.height//64*64)),"batch_size":1}},
      "5":{"class_type":"KSampler","inputs":{"seed":seed,"steps":max(15,min(50,req.steps)),"cfg":req.cfg,"sampler_name":"dpmpp_2m","scheduler":"karras","denoise":1.0,"model":["1",0],"positive":["2",0],"negative":["3",0],"latent_image":["4",0]}},
      "6":{"class_type":"VAEDecode","inputs":{"samples":["5",0],"vae":["1",2]}},
      "7":{"class_type":"SaveImage","inputs":{"filename_prefix":"universe_creator","images":["6",0]}}
    }
    return workflow

def wait_comfy(prompt_id, timeout=600):
    deadline=time.time()+timeout
    while time.time()<deadline:
        r=requests.get(f"{COMFY}/history/{prompt_id}", timeout=20)
        if r.ok:
            history=r.json().get(prompt_id)
            if history and history.get("outputs"):
                for node in history["outputs"].values():
                    for item in node.get("images", []):
                        image=requests.get(f"{COMFY}/view",params=item,timeout=60)
                        image.raise_for_status()
                        return image.content, item.get("filename","generated.png")
        time.sleep(2)
    raise TimeoutError("O ComfyUI excedeu o tempo de geração.")

@app.get("/")
def root(): return {"status":"online","system":"UniVerse Creator Engine","version":"2.0","engine":"ComfyUI"}
@app.get("/health")
def health():
    try:
        r=requests.get(f"{COMFY}/system_stats",timeout=8); r.raise_for_status()
        return {"status":"healthy","drive":ROOT.exists(),"comfyui":True}
    except Exception as e: return {"status":"degraded","drive":ROOT.exists(),"comfyui":False,"error":str(e)[:180]}

@app.post("/create_identity")
def create_identity(data: IdentityIn):
    if data.mode not in ("influencer","my_identity","ai_identity"):\n        raise HTTPException(400,"Modo de identidade inválido.")\n    identity_id=data.identityId or uuid.uuid4().hex
    folder=IDENTITIES/identity_id
    folder.mkdir(parents=True,exist_ok=True)
    metadata={"identityId":identity_id,"mode":data.mode,"name":data.name,"prompt":data.prompt,"createdAt":time.time(),"status":"registered"}
    if data.referenceImage:
        raw=decode_data_url(data.referenceImage)
        (folder/"reference.png").write_bytes(raw)
        metadata["reference"]="reference.png"
    (folder/"identity.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    return {"ok":True,"identityId":identity_id,"status":"registered","message":"Identidade registrada no Google Drive."}

@app.post("/generate_image")
def generate_image(data: ImageIn):
    identity_folder=IDENTITIES/(data.identityId or "")
    prompt=data.prompt
    if data.identityId and (identity_folder/"identity.json").exists():
        meta=json.loads((identity_folder/"identity.json").read_text())
        prompt += "\nConsistência da identidade: "+meta.get("prompt","")
    client_id=uuid.uuid4().hex
    try:
        queued=requests.post(f"{COMFY}/prompt",json={"prompt":comfy_prompt(data),"client_id":client_id},timeout=30)
        queued.raise_for_status()
        prompt_id=queued.json()["prompt_id"]
        image_bytes, filename=wait_comfy(prompt_id)
    except Exception as e:
        raise HTTPException(502, "Falha no ComfyUI: "+str(e)[:240])
    output_id=uuid.uuid4().hex
    out=GENERATED/(output_id+".png")
    out.write_bytes(image_bytes)
    return {"ok":True,"status":"succeeded","imageBase64":base64.b64encode(image_bytes).decode("ascii"),"mimeType":"image/png","outputId":output_id,"drivePath":str(out),"promptId":prompt_id}

@app.post("/train_lora")
def train_lora(payload: dict):
    identity_id=str(payload.get("identityId",""))
    folder=IDENTITIES/identity_id
    if not identity_id or not folder.exists(): raise HTTPException(404,"Identidade não encontrada no Drive.")
    dataset=folder/"dataset"
    if not dataset.exists() or not any(dataset.glob("*")): raise HTTPException(400,"Adicione fotos de treinamento à pasta dataset da identidade.")
    script=Path("/content/kohya_ss/sd-scripts/train_network.py")
    if not script.exists(): raise HTTPException(503,"Kohya_ss ainda não foi instalado neste runtime.")
    return {"ok":False,"status":"needs_dataset_config","message":"Dataset encontrado. Configure captions e parâmetros de treinamento antes de iniciar para evitar um LoRA inconsistente."}

@app.post("/generate_video")
def generate_video(payload: dict):
    raise HTTPException(503,"AnimateDiff ainda não está configurado neste runtime. Instale os nós AnimateDiff-Evolved e o motion module compatível no ComfyUI.")

