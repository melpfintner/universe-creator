import { useEffect, useRef, useState } from "react";

function CampaignBriefing(){
  const [data,setData]=useState({brand:"",product:"",objective:"",audience:"",message:"",format:"Reels / TikTok",notes:""});
  const change=e=>setData({...data,[e.target.name]:e.target.value});
  return <section className="panel"><div className="eyebrow">CAMPANHAS</div><h1>Briefing da campanha</h1><p className="intro">Organize as informações da marca e o objetivo do conteúdo antes de criar seu vídeo UGC.</p><div className="form-grid"><label>Marca<input name="brand" value={data.brand} onChange={change} placeholder="Nome da marca"/></label><label>Produto ou serviço<input name="product" value={data.product} onChange={change} placeholder="O que será divulgado?"/></label><label>Objetivo da campanha<input name="objective" value={data.objective} onChange={change} placeholder="Apresentar, vender, gerar reconhecimento"/></label><label>Público-alvo<input name="audience" value={data.audience} onChange={change} placeholder="Para quem é o conteúdo?"/></label><label className="wide">Mensagem principal<textarea name="message" value={data.message} onChange={change} rows="3" placeholder="Qual informação precisa aparecer no vídeo?"/></label><label>Formato<select name="format" value={data.format} onChange={change}><option>Reels / TikTok</option><option>Stories</option><option>Vídeo para anúncio</option><option>Unboxing</option><option>Depoimento / Review</option></select></label><label className="wide">Observações e entregáveis<textarea name="notes" value={data.notes} onChange={change} rows="3" placeholder="Duração, cenas obrigatórias, tom de voz e CTA."/></label></div></section>
}

function UGCPhotoForm(){
  const [photo,setPhoto]=useState(null),[preview,setPreview]=useState(""),[prompt,setPrompt]=useState(""),[count,setCount]=useState("1"),[duration,setDuration]=useState(""),[voice,setVoice]=useState("none"),[language,setLanguage]=useState("pt-BR"),[narrationLanguage,setNarrationLanguage]=useState("pt-BR"),[voiceSample,setVoiceSample]=useState(null),[status,setStatus]=useState("");
  const fileRef=useRef(null);
  useEffect(()=>()=>{if(preview)URL.revokeObjectURL(preview)},[preview]);
  function acceptFile(file){if(!file)return;if(!["image/jpeg","image/png","image/webp"].includes(file.type)){setStatus("Selecione uma imagem JPG, PNG ou WEBP.");return}setPhoto(file);setPreview(URL.createObjectURL(file));setStatus("")}
  function onFile(e){acceptFile(e.target.files?.[0])}
  function onDrop(e){e.preventDefault();acceptFile(e.dataTransfer.files?.[0])}
  useEffect(()=>{function paste(e){const items=e.clipboardData?.items;if(!items)return;for(const item of items){if(/^image\\/(png|jpeg|webp)$/.test(item.type)){const f=item.getAsFile();if(f){e.preventDefault();acceptFile(f);break}}}}document.addEventListener("paste",paste);return()=>document.removeEventListener("paste",paste)},[]);
  function submit(custom){if(!photo){setStatus("Adicione uma foto de referência para continuar.");return}if(!duration){setStatus("Selecione a duração do vídeo.");return}if(custom&&!prompt.trim()){setStatus("No modo personalizado, escreva um prompt com os ajustes desejados.");return}setStatus("Foto e configurações preparadas. A geração real depende da conexão validada com o motor de vídeo. Nenhum vídeo foi criado ou simulado.")}
  return <>
    <section className="original-video-panel">
      <div className="flow-grid"><section className="flow-card active"><h2>FOTO</h2><p className="muted">Use foto do produto ou outra referência. Não precisa de briefing, link nem roteiro.</p>
        <div className="original-upload" role="button" tabIndex="0" onClick={()=>fileRef.current?.click()} onKeyDown={e=>e.key==="Enter"&&fileRef.current?.click()} onDragOver={e=>e.preventDefault()} onDrop={onDrop}>
          <strong>＋ Adicionar foto de referência</strong><span className="note">JPG, PNG ou WEBP · Arraste uma foto aqui ou copie e cole (Ctrl+V / ⌘V)</span>
          <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" onChange={onFile}/>
          {photo&&<span className="selected-file">{photo.name}</span>}
        </div>
        {preview&&<div className="original-preview"><img src={preview} alt="Pré-visualização da foto de referência"/></div>}
      </section></div>
      <div className="prompt-shared"><label className="field" htmlFor="simplePrompt">Prompt <small>(opcional)</small></label><textarea id="simplePrompt" value={prompt} onChange={e=>setPrompt(e.target.value)} placeholder="Se quiser, diga algo breve sobre o estilo ou objetivo do vídeo."/></div>
      <div className="grid2"><div><label className="field" htmlFor="campaignCount">Quantidade de vídeos na sequência</label><select id="campaignCount" className="control" value={count} onChange={e=>setCount(e.target.value)}>{[1,2,3,4,5,6].map(n=><option key={n} value={n}>{n} {n===1?"vídeo":"vídeos"}</option>)}</select></div><div><label className="field" htmlFor="duration">Duração</label><select id="duration" className="control" value={duration} onChange={e=>setDuration(e.target.value)}><option value="">Selecione</option><option value="15">15 segundos</option><option value="20">20 segundos</option><option value="30">30 segundos</option><option value="60">Até 60 segundos (se suportado)</option></select></div></div>
      <label className="field">Narração</label><div className="choice-row"><label className="choice"><input type="radio" name="voice" value="none" checked={voice==="none"} onChange={e=>setVoice(e.target.value)}/> Sem voz</label><label className="choice"><input type="radio" name="voice" value="user" checked={voice==="user"} onChange={e=>setVoice(e.target.value)}/> Minha voz</label><label className="choice"><input type="radio" name="voice" value="influencer" checked={voice==="influencer"} onChange={e=>setVoice(e.target.value)}/> Voz de influencer IA</label></div>
      <div className="grid2"><div><label className="field" htmlFor="language">Idioma do vídeo</label><select id="language" className="control" value={language} onChange={e=>setLanguage(e.target.value)}><option value="pt-BR">Português</option><option value="en">Inglês</option><option value="es">Espanhol</option></select></div><div><label className="field" htmlFor="voiceSample">Amostra de voz <small>(opcional, conforme suporte)</small></label><input id="voiceSample" className="control" type="file" accept="audio/*" onChange={e=>setVoiceSample(e.target.files?.[0]||null)}/><p className="note">A amostra em português pode orientar a voz em outro idioma somente se o provedor oferecer clonagem multilíngue real.</p>{voiceSample&&<p className="selected-file">{voiceSample.name}</p>}</div></div>
      <p className="note">A criação deve usar benefícios verificáveis e uma narrativa adequada ao briefing ou ao que for visível na foto. Música não será adicionada automaticamente.</p>
      <div className="actions"><button className="action" type="button" onClick={()=>submit(false)}>✦ Gerar automaticamente</button><button className="action secondary" type="button" onClick={()=>submit(true)}>Gerar personalizado</button></div>
      {status&&<p className="status" role="status">{status}</p>}
    </section>
    <section className="original-video-panel narration-panel"><h2>Idioma da narração</h2><label className="field" htmlFor="narrationLanguage">Em qual idioma o vídeo deve falar?</label><select id="narrationLanguage" className="control" value={narrationLanguage} onChange={e=>setNarrationLanguage(e.target.value)}><option value="pt-BR">Português</option><option value="en">Inglês</option><option value="es">Espanhol</option></select><p className="hint">Escolha o idioma para este vídeo. O uso da sua voz em outro idioma depende do suporte do gerador.</p></section>
  </>
}

export default function App(){
  const [tab,setTab]=useState(new URLSearchParams(location.search).get("mode")==="campaign"?"campaign":"ugc");
  return <div className="app-shell"><aside className="sidebar"><strong>✧ UniVerse Creator</strong><span>Vídeos UGC e<br/>Campanhas</span><a href="/app">← Voltar ao início</a></aside><main className="main-content"><nav className="tabs" aria-label="Área de criação"><button className={tab==="campaign"?"tab active":"tab"} onClick={()=>setTab("campaign")}>Campanhas</button><button className={tab==="ugc"?"tab active":"tab"} onClick={()=>setTab("ugc")}>Vídeo UGC</button></nav>{tab==="campaign"?<CampaignBriefing/>:<UGCPhotoForm/>}</main></div>
}
