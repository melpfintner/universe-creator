import os, io, json, time, uuid, base64, shutil, subprocess, threading
from pathlib import Path
from typing import Optional
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ROOT=Path("/content/drive/MyDrive/UniVerseCreator")
IDENTITIES=ROOT/"identities"; GENERATED=ROOT/"generated"; LORAS=ROOT/"loras"
for p in (IDENTITIES,GENERATED,LORAS): p.mkdir(parents=True,exist_ok=True)
COMFY=os.getenv("COMFYUI_URL","http://127.0.0.1:8188").rstrip("/")
CHECKPOINT=os.getenv("COMFYUI_CHECKPOINT","sd_xl_base_1.0.safetensors")
CONTROLNET=os.getenv("COMFYUI_CONTROLNET","")
MOTION_MODULE=os.getenv("COMFYUI_MOTION_MODULE","")
SD15_CHECKPOINT=os.getenv("COMFYUI_SD15_CHECKPOINT","v1-5-pruned-emaonly.safetensors")
SVD_CHECKPOINT=os.getenv("COMFYUI_SVD_CHECKPOINT","")
app=FastAPI(title="UniVerse Creator Engine",version="3.0")
jobs={}

class IdentityIn(BaseModel):
    module:Optional[str]=None; action:Optional[str]=None
    mode:str="influencer"; name:str=""; prompt:str=Field(min_length=8,max_length=5000)
    referenceImage:Optional[str]=None; identityId:Optional[str]=None
class ImageIn(BaseModel):
    module:Optional[int]=2; action:Optional[str]="generate_image"
    prompt:str=Field(min_length=8,max_length=5000); identityId:Optional[str]=None
    referenceImage:Optional[str]=None; controlImage:Optional[str]=None
    controlnet:bool=False; lora:Optional[str]=None
    width:int=1024; height:int=1024; steps:int=28; cfg:float=6.5
    seed:Optional[int]=None
    negativePrompt:str="blurry, low quality, deformed hands, extra fingers, watermark, text, logo"

def decode_data_url(value):
    if not value or "," not in value: raise HTTPException(400,"Imagem inválida.")
    head,payload=value.split(",",1)
    if not head.startswith("data:image/"): raise HTTPException(415,"A referência precisa ser uma imagem.")
    try: return base64.b64decode(payload)
    except Exception: raise HTTPException(400,"Não foi possível decodificar a imagem.")
def comfy_upload(raw,name):
    r=requests.post(COMFY+"/upload/image",files={"image":(name,raw,"image/png")},data={"overwrite":"true"},timeout=60)
    r.raise_for_status(); return r.json()["name"]
def queue_workflow(workflow,timeout=900):
    q=requests.post(COMFY+"/prompt",json={"prompt":workflow,"client_id":uuid.uuid4().hex},timeout=30); q.raise_for_status()
    pid=q.json()["prompt_id"]; deadline=time.time()+timeout
    while time.time()<deadline:
        h=requests.get(f"{COMFY}/history/{pid}",timeout=20)
        if h.ok:
            entry=h.json().get(pid)
            if entry and entry.get("status",{}).get("status_str")=="error":
                raise RuntimeError(str(entry["status"].get("messages","ComfyUI workflow error"))[:700])
            if entry and entry.get("outputs"):
                files=[]
                for node in entry["outputs"].values():
                    files += node.get("images",[])+node.get("gifs",[])+node.get("videos",[])
                if files:
                    item=files[0]; data=requests.get(COMFY+"/view",params=item,timeout=120); data.raise_for_status()
                    return data.content,item,pid
        time.sleep(2)
    raise TimeoutError("O ComfyUI excedeu o tempo limite.")
def build_image_workflow(req,control_name=None,reference_name=None):
    seed=req.seed if req.seed is not None else int(time.time()*1000)%2147483647
    w=max(512,min(1536,req.width//64*64)); h=max(512,min(1536,req.height//64*64))
    wf={
      "1":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":CHECKPOINT}},
      "2":{"class_type":"CLIPTextEncode","inputs":{"text":req.prompt,"clip":["1",1]}},
      "3":{"class_type":"CLIPTextEncode","inputs":{"text":req.negativePrompt,"clip":["1",1]}},
      "4":{"class_type":"EmptyLatentImage","inputs":{"width":w,"height":h,"batch_size":1}},
      "5":{"class_type":"KSampler","inputs":{"seed":seed,"steps":max(15,min(50,req.steps)),"cfg":req.cfg,"sampler_name":"dpmpp_2m","scheduler":"karras","denoise":1.0,"model":["1",0],"positive":["2",0],"negative":["3",0],"latent_image":["4",0]}},
      "6":{"class_type":"VAEDecode","inputs":{"samples":["5",0],"vae":["1",2]}},
      "7":{"class_type":"SaveImage","inputs":{"filename_prefix":"universe_creator","images":["6",0]}}
    }
    if req.lora:
        lora_path=LORAS/(Path(req.lora).name)
        if not lora_path.exists(): raise HTTPException(404,"LoRA solicitado não encontrado no Drive.")
        wf["8"]={"class_type":"LoraLoader","inputs":{"model":["1",0],"clip":["1",1],"lora_name":lora_path.name,"strength_model":0.8,"strength_clip":0.8}}
        wf["2"]["inputs"]["clip"]=["8",1]; wf["3"]["inputs"]["clip"]=["8",1]; wf["5"]["inputs"]["model"]=["8",0]
    if req.controlnet:
        if not CONTROLNET: raise HTTPException(503,"Defina COMFYUI_CONTROLNET com o nome do modelo ControlNet instalado.")
        if not control_name: raise HTTPException(400,"Envie controlImage para aplicar ControlNet.")
        wf["9"]={"class_type":"LoadImage","inputs":{"image":control_name}}
        wf["10"]={"class_type":"ControlNetLoader","inputs":{"control_net_name":CONTROLNET}}
        wf["11"]={"class_type":"ControlNetApplyAdvanced","inputs":{"positive":["2",0],"negative":["3",0],"control_net":["10",0],"image":["9",0],"strength":0.8,"start_percent":0.0,"end_percent":1.0,"vae":["1",2]}}
        wf["5"]["inputs"]["positive"]=["11",0]; wf["5"]["inputs"]["negative"]=["11",1]
    return wf

@app.get("/")
def root(): return {"status":"online","system":"UniVerse Creator Engine","version":"3.0","engine":"ComfyUI"}
@app.get("/health")
def health():
    try:
        r=requests.get(COMFY+"/system_stats",timeout=8); r.raise_for_status()
        models=[p.name for p in (Path("/content/ComfyUI/models/checkpoints")).glob("*.safetensors")]
        return {"status":"healthy","drive":ROOT.exists(),"comfyui":True,"checkpoint":CHECKPOINT in models,"controlnet_configured":bool(CONTROLNET),"animatediff_configured":bool(MOTION_MODULE),"svd_configured":bool(SVD_CHECKPOINT),"kohya_installed":Path("/content/kohya_ss/sd-scripts/train_network.py").exists()}
    except Exception as e: return {"status":"degraded","drive":ROOT.exists(),"comfyui":False,"error":str(e)[:180]}
@app.post("/create_identity")
def create_identity(data:IdentityIn):
    if data.mode not in ("influencer","my_identity","ai_identity"): raise HTTPException(400,"Modo de identidade inválido.")
    iid=data.identityId or uuid.uuid4().hex; folder=IDENTITIES/iid; folder.mkdir(parents=True,exist_ok=True)
    meta={"identityId":iid,"mode":data.mode,"name":data.name,"prompt":data.prompt,"createdAt":time.time(),"status":"registered"}
    if data.referenceImage:
        raw=decode_data_url(data.referenceImage); (folder/"reference.png").write_bytes(raw); meta["reference"]="reference.png"
    (folder/"identity.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2))
    return {"ok":True,"identityId":iid,"status":"registered","message":"Identidade e referência salvas no Google Drive."}
@app.post("/identity/{identity_id}/dataset")
def add_dataset(identity_id:str,payload:dict):
    folder=IDENTITIES/identity_id
    if not (folder/"identity.json").exists(): raise HTTPException(404,"Identidade não encontrada.")
    images=payload.get("images") or []
    if not images: raise HTTPException(400,"Envie imagens para o conjunto de treinamento.")
    ds=folder/"dataset"; ds.mkdir(exist_ok=True); saved=[]
    for i,item in enumerate(images):
        raw=decode_data_url(item); name=f"training_{int(time.time())}_{i:03d}.png"; (ds/name).write_bytes(raw); saved.append(name)
    return {"ok":True,"saved":len(saved),"files":saved}
@app.post("/generate_image")
def generate_image(data:ImageIn):
    folder=IDENTITIES/(data.identityId or ""); prompt=data.prompt
    if data.identityId and (folder/"identity.json").exists():
        meta=json.loads((folder/"identity.json").read_text()); prompt+="\nIdentity description: "+meta.get("prompt","")
    data.prompt=prompt
    if data.identityId and not data.lora:
        trained=LORAS/data.identityId
        candidates=sorted(trained.glob("*.safetensors")) if trained.exists() else []
        if candidates: data.lora=candidates[-1].name
    try:
        control_name=comfy_upload(decode_data_url(data.controlImage),"uvc_control.png") if data.controlImage else None
        wf=build_image_workflow(data,control_name)
        image,item,pid=queue_workflow(wf)
    except HTTPException: raise
    except Exception as e: raise HTTPException(502,"Falha no ComfyUI: "+str(e)[:300])
    oid=uuid.uuid4().hex; out=GENERATED/(oid+".png"); out.write_bytes(image)
    return {"ok":True,"status":"succeeded","imageBase64":base64.b64encode(image).decode(),"mimeType":"image/png","outputId":oid,"drivePath":str(out),"promptId":pid,"engine":"ComfyUI"}
@app.post("/train_lora")
def train_lora(payload:dict):
    iid=str(payload.get("identityId","")); folder=IDENTITIES/iid
    if not iid or not (folder/"identity.json").exists(): raise HTTPException(404,"Identidade não encontrada.")
    ds=folder/"dataset"
    imgs=[p for p in ds.glob("*") if p.suffix.lower() in (".png",".jpg",".jpeg",".webp")] if ds.exists() else []
    if len(imgs)<5: raise HTTPException(400,"O treinamento LoRA exige pelo menos 5 imagens na pasta dataset.")
    script=Path("/content/kohya_ss/sd-scripts/train_network.py")
    if not script.exists(): raise HTTPException(503,"Kohya_ss não está instalado neste runtime.")
    base=Path("/content/ComfyUI/models/checkpoints")/CHECKPOINT
    if not base.exists(): raise HTTPException(503,"Checkpoint configurado não encontrado.")
    meta=json.loads((folder/"identity.json").read_text()); token="uvc_"+iid[:8]
    train_root=folder/"kohya_dataset"; train_root.mkdir(exist_ok=True)
    train_dir=train_root/("10_"+token); train_dir.mkdir(exist_ok=True)
    for p in imgs:
        shutil.copy2(p,train_dir/p.name)
        caption=train_dir/(p.stem+".txt")
        if not caption.exists(): caption.write_text(token+", "+meta.get("prompt","").replace("\n"," ")[:500])
    output=LORAS/iid; output.mkdir(exist_ok=True)
    args=["python",str(script),"--pretrained_model_name_or_path",str(base),"--train_data_dir",str(train_root),"--output_dir",str(output),"--output_name",iid,"--resolution","1024,1024","--network_module","networks.lora","--network_dim",str(payload.get("networkDim",32)),"--network_alpha",str(payload.get("networkAlpha",16)),"--train_batch_size","1","--max_train_epochs",str(payload.get("epochs",8)),"--learning_rate","1e-4","--optimizer_type","AdamW8bit","--mixed_precision","fp16","--save_model_as","safetensors"]
    log=output/"training.log"
    try:
        with log.open("w") as fp: proc=subprocess.Popen(args,stdout=fp,stderr=subprocess.STDOUT,start_new_session=True)
    except Exception as e: raise HTTPException(500,"Não foi possível iniciar Kohya_ss: "+str(e)[:200])
    jobs[iid]={"pid":proc.pid,"log":str(log),"status":"running"}
    return {"ok":True,"status":"running","identityId":iid,"jobId":iid,"logPath":str(log),"message":"Treinamento LoRA iniciado no runtime."}
@app.get("/train_lora/{identity_id}/status")
def train_status(identity_id:str):
    job=jobs.get(identity_id); output=LORAS/identity_id
    if not job: return {"ok":True,"status":"unknown","loraReady":any(output.glob("*.safetensors"))}
    alive=Path(f"/proc/{job['pid']}").exists()
    tail=""
    try: tail="\n".join(Path(job["log"]).read_text(errors="ignore").splitlines()[-15:])
    except: pass
    ready=list(output.glob("*.safetensors"))
    return {"ok":True,"status":"running" if alive else ("succeeded" if ready else "failed"),"loraReady":bool(ready),"files":[p.name for p in ready],"logTail":tail}
@app.post("/generate_video_animatediff")
def generate_video_animatediff(payload:dict):
    if not MOTION_MODULE: raise HTTPException(503,"AnimateDiff não está configurado. Instale o motion module SD1.5.")
    checkpoint=Path("/content/ComfyUI/models/checkpoints")/SD15_CHECKPOINT
    motion=Path("/content/ComfyUI/models/animatediff_models")/MOTION_MODULE
    if not checkpoint.exists(): raise HTTPException(503,"Checkpoint SD1.5 não encontrado.")
    if not motion.exists(): raise HTTPException(503,"Motion module AnimateDiff não encontrado na pasta animatediff_models.")
    prompt=str(payload.get("prompt") or "cinematic natural movement, realistic motion")
    negative=str(payload.get("negativePrompt") or "blurry, low quality, flicker, distorted face, extra limbs")
    width=max(512,min(768,int(payload.get("width",512))//64*64))
    height=max(512,min(768,int(payload.get("height",512))//64*64))
    frames=max(8,min(32,int(payload.get("frames",16))))
    fps=max(4,min(12,int(payload.get("fps",8))))
    seed=int(payload.get("seed",int(time.time()*1000)%2147483647))
    wf={
      "1":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":SD15_CHECKPOINT}},
      "2":{"class_type":"CLIPTextEncode","inputs":{"text":prompt,"clip":["1",1]}},
      "3":{"class_type":"CLIPTextEncode","inputs":{"text":negative,"clip":["1",1]}},
      "4":{"class_type":"EmptyLatentImage","inputs":{"width":width,"height":height,"batch_size":frames}},
      "5":{"class_type":"ADE_AnimateDiffLoaderGen1","inputs":{"model":["1",0],"model_name":MOTION_MODULE,"beta_schedule":"autoselect"}},
      "6":{"class_type":"KSampler","inputs":{"seed":seed,"steps":max(15,min(30,int(payload.get("steps",20)))),"cfg":7.0,"sampler_name":"euler","scheduler":"normal","denoise":1.0,"model":["5",0],"positive":["2",0],"negative":["3",0],"latent_image":["4",0]}},
      "7":{"class_type":"VAEDecode","inputs":{"samples":["6",0],"vae":["1",2]}},
      "8":{"class_type":"VHS_VideoCombine","inputs":{"images":["7",0],"frame_rate":fps,"loop_count":0,"filename_prefix":"uvc_animatediff","format":"video/h264-mp4","pingpong":False,"save_output":True}}
    }
    try:
        _,item,pid=queue_workflow(wf,timeout=1800)
        video=requests.get(COMFY+"/view",params=item,timeout=180).content
        oid=uuid.uuid4().hex; out=GENERATED/(oid+".mp4"); out.write_bytes(video)
        return {"ok":True,"status":"succeeded","outputId":oid,"videoBase64":base64.b64encode(video).decode(),"mimeType":"video/mp4","drivePath":str(out),"promptId":pid,"engine":"AnimateDiff-Evolved"}
    except Exception as e: raise HTTPException(502,"Falha na geração AnimateDiff: "+str(e)[:250])

@app.post("/generate_video")
def generate_video(payload:dict):
    image_value=payload.get("image") or payload.get("referenceImage")
    if not image_value: raise HTTPException(400,"Envie uma imagem de referência para gerar vídeo.")
    try: image_name=comfy_upload(decode_data_url(image_value),"uvc_video_input.png")
    except Exception as e: raise HTTPException(400,"Imagem de entrada inválida: "+str(e)[:150])
    if SVD_CHECKPOINT:
        wf={
          "1":{"class_type":"ImageOnlyCheckpointLoader","inputs":{"ckpt_name":SVD_CHECKPOINT}},
          "2":{"class_type":"LoadImage","inputs":{"image":image_name}},
          "3":{"class_type":"SVD_img2vid_Conditioning","inputs":{"clip_vision":["1",1],"init_image":["2",0],"vae":["1",2],"width":int(payload.get("width",1024)),"height":int(payload.get("height",576)),"video_frames":int(payload.get("frames",25)),"motion_bucket_id":int(payload.get("motionBucketId",127)),"fps":int(payload.get("fps",6)),"augmentation_level":0.0}},
          "4":{"class_type":"KSampler","inputs":{"seed":int(payload.get("seed",42)),"steps":20,"cfg":2.5,"sampler_name":"euler","scheduler":"karras","denoise":1.0,"model":["1",0],"positive":["3",0],"negative":["3",1],"latent_image":["3",2]}},
          "5":{"class_type":"VAEDecode","inputs":{"samples":["4",0],"vae":["1",2]}},
          "6":{"class_type":"VHS_VideoCombine","inputs":{"images":["5",0],"frame_rate":int(payload.get("fps",6)),"loop_count":0,"filename_prefix":"uvc_svd","format":"video/h264-mp4","pingpong":False,"save_output":True}}
        }
    else:
        raise HTTPException(503,"SVD não está instalado. Configure COMFYUI_SVD_CHECKPOINT e instale os nós VideoHelperSuite.")
    try:
        _,item,pid=queue_workflow(wf,timeout=1800)
        video=requests.get(COMFY+"/view",params=item,timeout=180).content
        oid=uuid.uuid4().hex; out=GENERATED/(oid+".mp4"); out.write_bytes(video)
        return {"ok":True,"status":"succeeded","outputId":oid,"videoBase64":base64.b64encode(video).decode(),"mimeType":"video/mp4","drivePath":str(out),"promptId":pid,"engine":"Stable Video Diffusion"}
    except Exception as e: raise HTTPException(502,"Falha na geração de vídeo SVD: "+str(e)[:250])
