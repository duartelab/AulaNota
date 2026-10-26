const SERVIDOR_PADRAO = "http://127.0.0.1:8790";
const VALIDADE_ENVIADO_MS = 12 * 60 * 60 * 1000;

let cfg = { auto: true, autoYoutube: false, servidor: SERVIDOR_PADRAO };
const abas = new Map();
const jobs = new Map(); // persistido em storage.local
let ultimos = {}; // tabId -> último resultado, persistido em storage.local
let jobsCarregados = false;
let enviados = {};
let carregado = null;

const p = (fn, ...args) =>
  new Promise((res, rej) => {
    fn(...args, (r) => {
      const e = chrome.runtime.lastError;
      if (e) rej(new Error(e.message));
      else res(r);
    });
  });

async function carregar() {
  const dados = await p(chrome.storage.local.get, null);
  if (dados) {
    if (dados.cfg) cfg = Object.assign(cfg, dados.cfg);
    if (dados.enviados && typeof dados.enviados === "object") enviados = dados.enviados;
    if (dados.ultimos && typeof dados.ultimos === "object") ultimos = dados.ultimos;
    if (dados.jobs && typeof dados.jobs === "object") {
      for (const [k, v] of Object.entries(dados.jobs)) jobs.set(k, v);
      if (jobs.size) {
        try { chrome.alarms.create("aulanota-poll", { periodInMinutes: 0.5 }); } catch (e) {}
        setTimeout(consultarJobs, 3000);
      }
    }
  }
  carregado = true;
}
carregado = carregar().catch(() => { carregado = true; });

function limparEnviados() {
  const agora = Date.now();
  for (const [k, ts] of Object.entries(enviados)) {
    if (!ts || agora - ts > VALIDADE_ENVIADO_MS) delete enviados[k];
  }
}

async function salvar() {
  limparEnviados();
  try {
    await p(chrome.storage.local.set, {
      cfg,
      enviados,
      ultimos,
      jobs: Object.fromEntries(jobs)
    });
  } catch (e) {}
}

function registrarUltimo(tabId, job) {
  if (!tabId || !job) return;
  ultimos[String(tabId)] = {
    estado: job.estado || "",
    resultado: job.resultado || null,
    erro: job.erro || null,
    quando: job.concluido_em || new Date().toISOString(),
    videoTitulo: job.video_titulo || ""
  };
  salvar();
}

function marcar(texto, tabId) {  const opcoes = { text: texto || "" };
  if (tabId) opcoes.tabId = tabId;
  try { chrome.action.setBadgeBackgroundColor({ color: "#4338ca", tabId }); } catch (e) {}
  try { chrome.action.setBadgeText(opcoes); } catch (e) {}
}

function notificar(titulo, mensagem) {
  try {
    chrome.notifications.create("", {
      type: "basic",
      iconUrl: "icon128.png",
      title: titulo,
      message: mensagem
    });
  } catch (e) {}
}

function fetchJson(url, opcoes = {}, timeout = 12000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeout);
  return fetch(url, Object.assign({}, opcoes, { signal: ctrl.signal }))
    .then((r) => r.json().then((j) => ({ ok: r.ok, status: r.status, dados: j })))
    .finally(() => clearTimeout(t));
}

async function infoDaAba(tabId) {
  try {
    const tab = await p(chrome.tabs.get, tabId);
    return { url: tab.url || "", titulo: tab.title || "" };
  } catch (e) {
    return { url: "", titulo: "" };
  }
}

function estadoDaAba(tabId) {
  if (!abas.has(tabId)) {
    abas.set(tabId, {
      pagina: null, legenda: null, pendente: false, job: null,
      gerando: false, timerAuto: null
    });
  }
  return abas.get(tabId);
}

/* ---------- captura de CC sem depender do iframe aninhado ---------- */

const pendentesVideo = new Map(); // videoId -> { tabId, pagina, criado, manual }
const abasOcultas = new Map();    // aba oculta -> videoId

function extrairIdUrl(url) {
  const m = String(url || "").match(
    /(?:[?&]v=|youtu\.be\/|youtube(?:-nocookie)?\.com\/(?:embed|live|shorts)\/)([A-Za-z0-9_-]{11})/
  );
  return m ? m[1] : "";
}

function extrairObjetoJSON(texto, marcador) {
  const i = texto.indexOf(marcador);
  if (i < 0) return null;
  const inicio = texto.indexOf("{", i);
  if (inicio < 0) return null;
  let prof = 0, emStr = false, esc = false;
  for (let j = inicio; j < texto.length; j++) {
    const c = texto[j];
    if (emStr) {
      if (esc) esc = false;
      else if (c === "\\") esc = true;
      else if (c === '"') emStr = false;
    } else if (c === '"') {
      emStr = true;
    } else if (c === "{") {
      prof++;
    } else if (c === "}") {
      prof--;
      if (prof === 0) {
        try { return JSON.parse(texto.slice(inicio, j + 1)); } catch (e) { return null; }
      }
    }
  }
  return null;
}

function escolherTrilha(lista) {
  const manual = lista.filter((x) => x.kind !== "asr");
  const candidatas = manual.length ? manual : lista;
  for (const idioma of [navigator.language || "pt-BR", "pt-BR", "pt", "en"]) {
    const p = String(idioma).toLowerCase().slice(0, 2);
    const achou = candidatas.find((x) =>
      String(x.languageCode || "").toLowerCase().startsWith(p)
    );
    if (achou) return achou;
  }
  return candidatas[0];
}

async function legendasPorHTTP(videoId) {
  const paginas = [
    `https://www.youtube.com/embed/${videoId}?hl=pt&cc_load_policy=1`,
    `https://www.youtube-nocookie.com/embed/${videoId}?hl=pt&cc_load_policy=1`
  ];
  for (const url of paginas) {
    let html = "";
    try {
      const r = await fetch(url, { credentials: "include" });
      if (!r.ok) continue;
      html = await r.text();
    } catch (e) { continue; }

    const pr = extrairObjetoJSON(html, "ytInitialPlayerResponse");
    const tracks = pr && pr.captions && pr.captions.playerCaptionsTracklistRenderer
      && pr.captions.playerCaptionsTracklistRenderer.captionTracks;
    if (!Array.isArray(tracks) || !tracks.length) continue;

    const trilha = escolherTrilha(tracks);
    if (!trilha || !trilha.baseUrl) continue;

    let conteudo = "";
    try {
      const u = new URL(trilha.baseUrl);
      u.searchParams.set("fmt", "vtt");
      const r = await fetch(u.toString(), { credentials: "include" });
      if (r.ok) conteudo = await r.text();
      if (!conteudo.trim()) {
        const r2 = await fetch(trilha.baseUrl, { credentials: "include" });
        if (r2.ok) conteudo = await r2.text();
      }
    } catch (e) {}
    if (!conteudo.trim()) continue;

    const vd = (pr && pr.videoDetails) || {};
    return {
      videoId,
      titulo: vd.title || "",
      canal: vd.author || "",
      idioma: trilha.languageCode || "",
      auto: trilha.kind === "asr",
      formato: conteudo.indexOf("WEBVTT") >= 0 ? "vtt" : "auto",
      conteudo
    };
  }
  return null;
}

async function capturarVideo(tabId, videoId, pagina, manual) {
  if (!videoId) {
    return { ok: false, erro: "Vídeo do YouTube não identificado nesta página." };
  }
  const a = estadoDaAba(tabId);
  if (pagina) a.pagina = pagina;
  if (!a.legenda || a.legenda.videoId !== videoId) {
    a.legenda = {
      videoId,
      titulo: (a.legenda && a.legenda.titulo) || "",
      canal: (a.legenda && a.legenda.canal) || "",
      idioma: "",
      auto: false,
      formato: "vtt",
      conteudo: "",
      url: `https://www.youtube.com/watch?v=${videoId}`
    };
  }
  if (manual) marcar("…", tabId);
  return gerarAgora(tabId, true);
}

async function gerarAgora(tabId, forcar) {
  const a = estadoDaAba(tabId);
  const leg = a.legenda || {};
  const temTexto = !!(leg.conteudo && leg.conteudo.trim());
  const temVideo = !!(leg.videoId || leg.url);
  if (!temTexto && !temVideo) {
    return { ok: false, erro: "Vídeo não identificado. Use o link manual no popup." };
  }
  if (a.job && jobs.has(a.job)) {
    return { ok: true, job: a.job, estado: "ja_em_andamento" };
  }

  const pagina = a.pagina || (await infoDaAba(tabId));
  const chave = `${leg.videoId || "sem-id"}|${pagina.url || ""}`;
  const anterior = enviados[chave];
  if (!forcar && anterior && Date.now() - anterior < VALIDADE_ENVIADO_MS) {
    return { ok: true, estado: "ja_gerado", mensagem: "Notas desta aula já foram geradas." };
  }
  if (a.gerando) return { ok: true, estado: "em_andamento" };
  a.gerando = true;

  const corpo = {
    video_id: leg.videoId || "",
    video_url: leg.url || (leg.videoId ? `https://www.youtube.com/watch?v=${leg.videoId}` : ""),
    video_titulo: leg.titulo || "",
    canal: leg.canal || "",
    pagina_url: pagina.url || "",
    pagina_titulo: pagina.titulo || "",
    idioma: leg.idioma || "",
    auto: !!leg.auto
  };
  if (temTexto) {
    corpo.legenda = { formato: leg.formato || "vtt", conteudo: leg.conteudo };
  }

  marcar("…", tabId);
  let resposta;
  try {
    resposta = await fetchJson(`${cfg.servidor}/notas`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpo)
    }, 30000);
  } catch (e) {
    a.gerando = false;
    marcar("!", tabId);
    return { ok: false, erro: `Daemon local offline (${cfg.servidor}). Rode: aulanota serve` };
  }
  a.gerando = false;

  if (!resposta.ok || !resposta.dados || !resposta.dados.job) {
    marcar("!", tabId);
    return { ok: false, erro: (resposta.dados && resposta.dados.erro) || "Falha ao enviar a aula." };
  }

  const jid = resposta.dados.job;
  jobs.set(jid, {
    tabId,
    chave,
    videoTitulo: a.legenda.titulo || "",
    paginaTitulo: pagina.titulo || "",
    inicio: Date.now()
  });
  a.job = jid;
  delete ultimos[String(tabId)];
  salvar();
  notificar("AulaNota", "Gerando notas… você pode continuar assistindo.");
  try { chrome.alarms.create("aulanota-poll", { periodInMinutes: 0.5 }); } catch (e) {}
  setTimeout(consultarJobs, 3000);
  return { ok: true, job: jid, estado: "na_fila" };
}

let consultando = false;
async function consultarJobs() {
  if (consultando) return;
  consultando = true;
  try {
    for (const [jid, info] of [...jobs.entries()]) {
      let r;
      try {
        r = await fetchJson(`${cfg.servidor}/jobs/${jid}`);
      } catch (e) {
        continue;
      }
      if (!r.ok) {
        jobs.delete(jid);
        if (r.status === 404) {
          notificar("AulaNota", "O daemon reiniciou e não achou este trabalho. Clique em Gerar notas novamente.");
          registrarUltimo(info.tabId, {
            estado: "erro",
            erro: "O daemon reiniciou e perdeu este trabalho. Clique em Gerar notas novamente.",
            quando: new Date().toISOString()
          });
        }
        marcar("!", info.tabId);
        salvar();
        continue;
      }
      const d = r.dados || {};
      if (d.estado === "pronto" || d.estado === "ja_existe") {
        jobs.delete(jid);
        enviados[info.chave] = Date.now();
        const res = d.resultado || {};
        const linha = res.caminho ? String(res.caminho) : "";
        registrarUltimo(info.tabId, d);
        notificar("Notas prontas", `${res.disciplina || ""} · ${res.disciplina_nome || ""}\n${linha}`);
        marcar("✓", info.tabId);
        setTimeout(() => marcar("", info.tabId), 30000);
        salvar();
      } else if (d.estado === "erro") {
        jobs.delete(jid);
        registrarUltimo(info.tabId, d);
        notificar("AulaNota — erro", String(d.erro || "Falha ao gerar as notas.").slice(0, 300));
        marcar("!", info.tabId);
        salvar();
        setTimeout(() => marcar("", info.tabId), 30000);
      }
    }
  } finally {
    consultando = false;
  }
  if (jobs.size) {
    setTimeout(consultarJobs, 5000);
  } else {
    try { chrome.alarms.clear("aulanota-poll"); } catch (e) {}
  }
}

async function talvezAuto(tabId) {
  if (!cfg.auto) return;
  const a = abas.get(tabId);
  if (!a || !a.legenda || !a.legenda.conteudo) return;
  const pagina = a.pagina || (await infoDaAba(tabId));
  const noYoutube = /(^|\.)youtube\.com$|(^|\.)youtu\.be$/.test(
    (() => { try { return new URL(pagina.url).hostname; } catch (e) { return ""; } })()
  );
  if (noYoutube && !cfg.autoYoutube) return;
  if (!noYoutube && !a.pagina) return;
  await gerarAgora(tabId, false);
}

async function tratar(msg, remetente, responder) {
  const tabId = (remetente && remetente.tab && remetente.tab.id) || msg.tabId;

  if (msg.tipo === "pagina") {
    const a = estadoDaAba(tabId);
    const vistos = (a.pagina && a.pagina.embeds) || [];
    const novos = msg.embeds || [];
    a.pagina = {
      url: msg.url || "",
      titulo: msg.titulo || "",
      embeds: [...new Set([...novos, ...vistos])]
    };
    responder({ ok: true });
    talvezAuto(tabId);
    if (cfg.auto && a.pagina.embeds.length && !(a.legenda && a.legenda.conteudo)) {
      clearTimeout(a.timerAuto);
      a.timerAuto = setTimeout(() => {
        const atual = abas.get(tabId);
        if (!cfg.auto || !atual) return;
        if (atual.legenda && atual.legenda.conteudo) return;
        if (!atual.pagina || !atual.pagina.embeds.length) return;
        capturarVideo(tabId, atual.pagina.embeds[0], atual.pagina, false);
      }, 5000);
    }
    return;
  }

  if (msg.tipo === "legendas") {
    if (msg.conteudo && msg.videoId && pendentesVideo.has(msg.videoId)) {
      const info = pendentesVideo.get(msg.videoId);
      pendentesVideo.delete(msg.videoId);
      const alvo = estadoDaAba(info.tabId);
      if (info.pagina) alvo.pagina = info.pagina;
      alvo.legenda = {
        videoId: msg.videoId,
        titulo: msg.titulo || "",
        canal: msg.canal || "",
        idioma: msg.idioma || "",
        auto: !!msg.auto,
        formato: msg.formato || "vtt",
        conteudo: msg.conteudo
      };
      alvo.pendente = false;
      clearTimeout(alvo.timerAuto);
      const tabRemetente = remetente && remetente.tab && remetente.tab.id;
      if (tabRemetente && abasOcultas.get(tabRemetente) === msg.videoId) {
        abasOcultas.delete(tabRemetente);
        try { chrome.tabs.remove(tabRemetente); } catch (e) {}
      }
      responder({ ok: true });
      await gerarAgora(info.tabId, true);
      return;
    }

    const a = estadoDaAba(tabId);
    a.legenda = {
      videoId: msg.videoId || "",
      titulo: msg.titulo || "",
      canal: msg.canal || "",
      idioma: msg.idioma || "",
      auto: !!msg.auto,
      formato: msg.formato || "vtt",
      conteudo: msg.conteudo || ""
    };
    clearTimeout(a.timerAuto);
    responder({ ok: true });
    if (msg.conteudo) {
      if (a.pendente) {
        a.pendente = false;
        await gerarAgora(tabId, true);
      } else {
        talvezAuto(tabId);
      }
    }
    return;
  }

  if (msg.tipo === "sem_legenda") {
    const tabRemetente = remetente && remetente.tab && remetente.tab.id;
    const vidOculto = tabRemetente ? abasOcultas.get(tabRemetente) : null;
    if (vidOculto && pendentesVideo.has(vidOculto)) {
      const info = pendentesVideo.get(vidOculto);
      pendentesVideo.delete(vidOculto);
      abasOcultas.delete(tabRemetente);
      try { chrome.tabs.remove(tabRemetente); } catch (e) {}
      notificar("Sem legendas", "Este vídeo não tem CC disponível para gerar notas.");
      marcar("×", info.tabId);
      responder({ ok: true });
      return;
    }
    const a = estadoDaAba(tabId);
    a.legenda = null;
    marcar("×", tabId);
    if (a.pendente) {
      a.pendente = false;
      const motivo = msg.motivo || "";
      notificar(
        "Sem legendas",
        motivo === "download_vazio"
          ? "O vídeo tem CC, mas não consegui baixar a legenda. Recarregue a página e tente de novo."
          : "Este vídeo não tem CC disponível para gerar notas."
      );
    }
    responder({ ok: true });
    return;
  }

  if (msg.tipo === "gerar") {
    const a = estadoDaAba(tabId);
    const pagina = a.pagina || (await infoDaAba(tabId));
    a.pagina = Object.assign({ url: "", titulo: "", embeds: [] }, a.pagina || {}, {
      url: (a.pagina && a.pagina.url) || pagina.url,
      titulo: (a.pagina && a.pagina.titulo) || pagina.titulo
    });
    clearTimeout(a.timerAuto);
    if (!a.legenda || !a.legenda.conteudo) {
      const embeds = (a.pagina && a.pagina.embeds) || [];
      if (embeds.length) {
        const r = await capturarVideo(tabId, embeds[0], a.pagina, true);
        responder(r);
        return;
      }
      a.pendente = true;
      try {
        await p(chrome.tabs.sendMessage, tabId, { tipo: "pedir_legendas" });
      } catch (e) {
        a.pendente = false;
        responder({
          ok: false,
          erro: "A extensão não está ativa nesta aba. Recarregue a página (F5) ou use o link manual no popup."
        });
        return;
      }
      responder({ ok: true, estado: "pedindo_legenda" });
      return;
    }
    const r = await gerarAgora(tabId, true);
    responder(r);
    return;
  }

  if (msg.tipo === "gerar_url") {
    const id = extrairIdUrl(msg.url);
    if (!id) {
      responder({ ok: false, erro: "Link do YouTube inválido." });
      return;
    }
    const a = estadoDaAba(tabId);
    const pagina = a.pagina || (await infoDaAba(tabId));
    const r = await capturarVideo(tabId, id, pagina, true);
    responder(r);
    return;
  }

  if (msg.tipo === "config") {
    cfg = Object.assign(cfg, msg.cfg || {});
    await salvar();
    responder({ ok: true, cfg });
    return;
  }

  if (msg.tipo === "gerar_todas") {
    let tabs = [];
    try { tabs = await p(chrome.tabs.query, {}); } catch (e) {}
    let marcadas = 0;
    for (const tab of tabs) {
      if (!tab.id || !/^https?:/.test(tab.url || "")) continue;
      const a = estadoDaAba(tab.id);
      let host = "";
      try { host = new URL(tab.url).hostname; } catch (e) {}
      const noYoutube = /(^|\.)youtube\.com$|(^|\.)youtu\.be$/.test(host);
      if (!a.pagina) {
        if (noYoutube) {
          if (!cfg.autoYoutube) continue;
          a.pagina = { url: tab.url, titulo: tab.title || "", embeds: [] };
        } else {
          continue;
        }
      }
      a.pendente = true;
      try {
        await p(chrome.tabs.sendMessage, tab.id, { tipo: "pedir_legendas" });
        marcadas += 1;
      } catch (e) {}
    }
    responder({ ok: true, abas: marcadas });
    return;
  }

  if (msg.tipo === "status") {
    const a = abas.get(tabId) || {};
    let detalheJob = null;
    if (a.job) {
      try {
        const r = await fetchJson(`${cfg.servidor}/jobs/${a.job}`);
        detalheJob = r.ok ? r.dados : null;
      } catch (e) {}
      if (detalheJob && ["pronto", "ja_existe", "erro"].includes(detalheJob.estado)) {
        const info = jobs.get(a.job);
        if (info && info.chave) enviados[info.chave] = Date.now();
        jobs.delete(a.job);
        registrarUltimo(tabId, detalheJob);
        salvar();
        a.job = null;
        detalheJob = null;
      }
    }
    const ativo = detalheJob && !["pronto", "ja_existe", "erro"].includes(detalheJob.estado);
    responder({
      ok: true,
      cfg,
      daemon: ativo ? true : null,
      aba: {
        temLegenda: !!(a.legenda && a.legenda.conteudo),
        caracteres: (a.legenda && a.legenda.conteudo ? a.legenda.conteudo.length : 0),
        videoTitulo: (a.legenda && a.legenda.titulo) || "",
        videoId: (a.legenda && a.legenda.videoId) || "",
        idioma: (a.legenda && a.legenda.idioma) || "",
        auto: !!(a.legenda && a.legenda.auto),
        paginaUrl: (a.pagina && a.pagina.url) || "",
        paginaTitulo: (a.pagina && a.pagina.titulo) || "",
        embeds: (a.pagina && a.pagina.embeds) || []
      },
      job: ativo ? detalheJob : null,
      ultimo: ultimos[String(tabId)] || null
    });
    return;
  }

  responder({ ok: false, erro: "tipo desconhecido" });
}

chrome.runtime.onMessage.addListener((msg, remetente, responder) => {
  if (!msg || !msg.tipo) return false;
  Promise.resolve(carregado)
    .then(() => tratar(msg, remetente || {}, responder))
    .catch((e) => {
      try { responder({ ok: false, erro: String(e && e.message ? e.message : e) }); } catch (err) {}
    });
  return true;
});

try {
  chrome.alarms.onAlarm.addListener((alarme) => {
    if (alarme.name === "aulanota-poll") consultarJobs();
  });
} catch (e) {}

try {
  chrome.runtime.onInstalled.addListener(() => {
    p(chrome.storage.local.get, null).then((d) => {
      if (!d || !d.cfg) p(chrome.storage.local.set, { cfg });
    });
  });
} catch (e) {}

chrome.tabs.onRemoved.addListener((tabId) => {
  abas.delete(tabId);
  if (ultimos[String(tabId)]) {
    delete ultimos[String(tabId)];
    salvar();
  }
});

chrome.tabs.onUpdated.addListener((tabId, info) => {
  if (info.status === "loading") {
    const a = abas.get(tabId);
    if (a) a.legenda = null;
  }
});
