/* Roda no "main world" do YouTube: consegue ler ytInitialPlayerResponse
   e buscar o arquivo de legendas com a sessão do usuário. Nunca baixa vídeo. */
(() => {
  if (window.__aulanotaMain) return;
  window.__aulanotaMain = true;

  const MARCA = "__aulanota";
  const post = (obj) => window.postMessage(Object.assign({ [MARCA]: true }, obj), "*");

  function idDoVideo() {
    const p = location.pathname;
    const m = p.match(/\/(?:embed|shorts|live|v)\/([A-Za-z0-9_-]{6,})/);
    if (m) return m[1];
    return new URLSearchParams(location.search).get("v") || "";
  }

  function respostaDoPlayer() {
    if (window.ytInitialPlayerResponse) return window.ytInitialPlayerResponse;
    const p = document.getElementById("movie_player");
    if (p && typeof p.getPlayerResponse === "function") {
      try { return p.getPlayerResponse(); } catch (e) {}
    }
    return null;
  }

  function trilhas() {
    const pr = respostaDoPlayer();
    const diretas = pr && pr.captions && pr.captions.playerCaptionsTracklistRenderer
      && pr.captions.playerCaptionsTracklistRenderer.captionTracks;
    if (Array.isArray(diretas) && diretas.length) return diretas;
    try {
      const p = document.getElementById("movie_player");
      if (p && typeof p.getOption === "function") {
        return p.getOption("captions", "tracklist") || [];
      }
    } catch (e) {}
    return [];
  }

  function escolher(lista) {
    const manual = lista.filter((t) => t.kind !== "asr");
    const candidatas = manual.length ? manual : lista;
    const idiomas = [navigator.language || "pt-BR", "pt-BR", "pt", "en"];
    for (const idioma of idiomas) {
      const prefixo = String(idioma).toLowerCase().slice(0, 2);
      const achou = candidatas.find((t) => String(t.languageCode || "").toLowerCase().startsWith(prefixo));
      if (achou) return achou;
    }
    return candidatas[0];
  }

  async function baixarLegenda(trilha) {
    const url = new URL(trilha.baseUrl);
    url.searchParams.set("fmt", "vtt");
    try {
      const r = await fetch(url.toString(), { credentials: "include" });
      if (r.ok) {
        const texto = await r.text();
        if (texto && texto.trim()) return texto;
      }
    } catch (e) {}
    try {
      const r = await fetch(trilha.baseUrl, { credentials: "include" });
      if (r.ok) return await r.text();
    } catch (e) {}
    return "";
  }

  let extraindo = false;

  function esperarTrilhas(ms) {
    return new Promise((res) => {
      const inicio = Date.now();
      const timer = setInterval(() => {
        const lista = trilhas();
        if (lista.length || Date.now() - inicio >= ms) {
          clearInterval(timer);
          res(lista);
        }
      }, 400);
    });
  }

  async function extrair(motivo) {
    if (extraindo) return;
    extraindo = true;
    try {
      let lista = trilhas();
      if (!lista.length) lista = await esperarTrilhas(motivo === "popup" ? 10000 : 6000);
      const videoId = idDoVideo();
      const pr = respostaDoPlayer() || {};
      const vd = pr.videoDetails || {};
      if (!lista.length) {
        post({
          tipo: "sem_legenda",
          videoId,
          motivo: "sem_trilha",
          titulo: vd.title || document.title
        });
        return;
      }
      const trilha = escolher(lista);
      const conteudo = await baixarLegenda(trilha);
      if (!conteudo || !conteudo.trim()) {
        post({
          tipo: "sem_legenda",
          videoId: vd.videoId || videoId,
          motivo: "download_vazio",
          titulo: vd.title || document.title
        });
        return;
      }
      post({
      tipo: "legendas",
        videoId: vd.videoId || videoId,
        titulo: vd.title || document.title.replace(/\s*-\s*YouTube\s*$/, ""),
        canal: vd.author || "",
        idioma: trilha.languageCode || "",
        auto: trilha.kind === "asr",
        formato: conteudo.indexOf("WEBVTT") >= 0 ? "vtt" : "auto",
        conteudo,
        duracao: vd.lengthSeconds || null,
        motivo: String(motivo || "")
      });
    } finally {
      extraindo = false;
    }
  }

  window.addEventListener("message", (e) => {
    if (e.source === window && e.data && e.data.__aulanota_pedido) {
      extrair(e.data.motivo || "pedido");
    }
  });

  let tentativas = 0;
  const timer = setInterval(() => {
    tentativas += 1;
    if (trilhas().length) {
      clearInterval(timer);
      extrair("auto");
    } else if (tentativas >= 40) {
      clearInterval(timer);
      extrair("timeout");
    }
  }, 700);

  window.addEventListener("yt-navigate-finish", () => {
    setTimeout(() => extrair("navegacao"), 1200);
  });
})();
