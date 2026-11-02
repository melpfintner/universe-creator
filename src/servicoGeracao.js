// Adaptador isolado para o endpoint do notebook Colab/Gradio.
// A rota e o formato do payload precisam ser confirmados no notebook antes do uso.
// Não coloque tokens privados em variáveis VITE_*.
const ENDPOINT_COLAB = import.meta.env.VITE_COLAB_ENDPOINT;

export function montarPromptUGC({ movimento, estilo, orientacao, orientacaoCena }) {
  return [
    "Vídeo UGC realista, gravado como conteúdo lifestyle",
    movimento || "gestos naturais e interação espontânea",
    estilo || "natural e espontâneo",
    orientacao || "vertical 9:16",
    orientacaoCena || "",
    "movimentos corporais contínuos, expressões naturais, iluminação realista"
  ].filter(Boolean).join(", ");
}

export async function dispararGeracaoVideoUGC(dadosFormulario) {
  if (!ENDPOINT_COLAB) {
    return { sucesso: false, mensagem: "O endpoint do Colab ainda não foi configurado." };
  }

  let endpoint;
  try {
    endpoint = new URL(ENDPOINT_COLAB);
    if (!["https:", "http:"].includes(endpoint.protocol)) throw new Error();
  } catch {
    return { sucesso: false, mensagem: "A URL do endpoint Colab é inválida." };
  }

  // Não enviar requisição até confirmar no notebook o endpoint, os inputs
  // e a ordem dos parâmetros. O protocolo moderno do Gradio pode exigir
  // /gradio_api/call/<api_name> e uma segunda consulta pelo event_id.
  if (/\/run\/predict\/?$/.test(endpoint.pathname)) {
    const prompt = montarPromptUGC(dadosFormulario);
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          data: [
            dadosFormulario.influencer_id ?? null,
            prompt,
            Number(dadosFormulario.duracao) || 15
          ]
        })
      });
      const result = await response.json().catch(() => null);
      if (!response.ok) throw new Error(result?.error || result?.detail || `HTTP ${response.status}`);
      const item = result?.data?.[0] ?? result?.output;
      const videoUrl = typeof item === "string" ? item : item?.url || item?.video?.url || item?.path;
      if (!videoUrl) throw new Error("A resposta não contém uma URL de vídeo reconhecida.");
      return { sucesso: true, videoUrl, prompt };
    } catch (error) {
      return { sucesso: false, mensagem: `Falha ao chamar o Colab: ${error.message}` };
    }
  }

  return {
    sucesso: false,
    mensagem: "O endpoint foi configurado, mas o protocolo do Gradio ainda precisa ser confirmado pelo notebook antes da integração."
  };
}
