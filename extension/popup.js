const $ = (id) => document.getElementById(id);
let tabId = null;
let servidor = "http://127.0.0.1:8790";
let timer = null;
let ultimoCaminho = "";

const pedir = (tipo, extra) =>
  new Promise((res) => {
    chrome.runtime.sendMessage(Object.assign({ tipo, tabId }, extra || {}), (r) => res(r || { ok: false }));
  });

function definirMsg(texto, classe) {
  const el = $("msg");
  el.textContent = texto || "";
  el.className = "msg" + (classe ? " " + classe : "");
}

async function verificarDaemon() {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 3000);
    const r = await fetch(`${servidor}/health`, { signal: ctrl.signal });
    clearTimeout(t);
    const d = await r.json();
    const el = $("daemon");
    el.textContent = d.ollama ? "local · online" : "Ollama offline";
    el.className = "pill " + (d.ollama ? "on" : "off");
    $("servidor").textContent = servidor.replace(/^https?:\/\//, "");
    $("vault").title = d.vault || "";
    return d;
  } catch (e) {
    const el = $("daemon");
    el.textContent = "daemon offline";
    el.className = "pill off";
    return null;
  }
}

async function recentes() {
  try {
    const r = await fetch(`${servidor}/recentes?limite=3`);
    const d = await r.json();
    const ul = $("recentes");
    ul.innerHTML = "";
    if (!d.notas || !d.notas.length) {
      ul.innerHTML = "<li>Nenhuma nota ainda.<span>Gere a primeira em uma aula.</span></li>";
      return;
    }
    for (const n of d.notas) {
      const li = document.createElement("li");
      li.textContent = n.titulo || n.video_id;
      const sp = document.createElement("span");
      sp.textContent = `${n.data} · ${n.disciplina}`;
      li.appendChild(sp);
      li.addEventListener("click", () => {
        navigator.clipboard.writeText(n.caminho || "");
        definirMsg("Caminho copiado.", "ok");
      });
      ul.appendChild(li);
    }
  } catch (e) {}
}

function mostrarAba(aba) {
  const video = $("video");
  const pagina = $("pagina");
  if (aba && aba.videoTitulo) {
    video.textContent = aba.videoTitulo;
  } else if (aba && aba.videoId) {
    video.textContent = `Vídeo ${aba.videoId}`;
  } else {
    video.textContent = "Nenhum vídeo com CC detectado";
  }
  const partes = [];
  if (aba && !aba.temLegenda && aba.embeds && aba.embeds.length) {
    video.textContent = `Vídeo do YouTube detectado (${aba.embeds[0]})`;
  }
  if (aba && aba.temLegenda) {
    const n = aba.caracteres ? Math.round(aba.caracteres / 1000) + " mil" : "";
    partes.push(`CC ${aba.idioma || ""}${aba.auto ? " (auto)" : ""}`.trim() + (n ? ` · ${n} caracteres` : ""));
  } else if (aba && aba.embeds && aba.embeds.length) {
    partes.push("clique em Gerar — o CC será buscado direto do vídeo");
  } else {
    partes.push("CC não detectado — recarregue (F5) ou use o link abaixo");
  }
  if (aba && aba.paginaTitulo) partes.push(aba.paginaTitulo);
  pagina.textContent = partes.join(" · ");
}

function horaCurta(iso) {
  try {
    const d = iso ? new Date(iso) : new Date();
    return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  } catch (e) {
    return "";
  }
}

function mostrarJob(job, ultimo) {
  const el = $("job");
  const info = job || ultimo;
  if (!info) {
    ultimoCaminho = "";
    el.classList.add("oculto");
    el.innerHTML = "";
    return;
  }
  el.classList.remove("oculto");
  el.innerHTML = "";
  const texto = document.createElement("div");

  if (info.estado === "erro") {
    texto.textContent = `Erro às ${horaCurta(info.concluido_em || info.quando)}: ` + (info.erro || "falha desconhecida");
  } else if (info.estado === "pronto" || info.estado === "ja_existe") {
    const r = (job ? job.resultado : ultimo.resultado) || {};
    ultimoCaminho = r.caminho || "";
    const quando = job ? job.concluido_em : ultimo.quando;
    texto.textContent =
      `${info.estado === "ja_existe" ? "Nota já existente" : "Nota pronta"} às ${horaCurta(quando)}` +
      ` — ${r.disciplina || ""}\n${r.caminho || ""}`;
  } else {
    const pr = info.progresso || {};
    const etapa = pr.etapa || (info.estado === "na_fila" ? "na fila" : "gerando notas");
    const partes = pr.parte && pr.total ? ` (${pr.parte}/${pr.total})` : "";
    texto.textContent = "Processando… " + etapa + partes;
  }
  el.appendChild(texto);

  if (ultimoCaminho && (info.estado === "pronto" || info.estado === "ja_existe")) {
    const b = document.createElement("button");
    b.className = "secundario";
    b.textContent = "Copiar caminho da nota";
    b.addEventListener("click", () => {
      navigator.clipboard.writeText(ultimoCaminho);
      definirMsg("Caminho copiado.", "ok");
    });
    el.appendChild(b);
  }
}

function agendar() {
  clearTimeout(timer);
  timer = setTimeout(atualizar, 2500);
}

async function atualizar() {
  const s = await pedir("status");
  if (s && s.cfg) {
    servidor = s.cfg.servidor || servidor;
    $("auto").checked = !!s.cfg.auto;
    $("autoYoutube").checked = !!s.cfg.autoYoutube;
  }
  if (s && s.aba) mostrarAba(s.aba);
  if (s && s.job) {
    mostrarJob(s.job, null);
    if (s.job.estado && !["pronto", "ja_existe", "erro"].includes(s.job.estado)) {
      agendar();
    }
  } else if (s && s.ultimo) {
    mostrarJob(null, s.ultimo);
  } else {
    mostrarJob(null, null);
  }
}

async function iniciar() {
  const tabs = await new Promise((r) => chrome.tabs.query({ active: true, currentWindow: true }, r));
  if (tabs && tabs[0]) tabId = tabs[0].id;

  await verificarDaemon();
  await atualizar();
  recentes();

  $("gerar").addEventListener("click", async () => {
    const b = $("gerar");
    b.disabled = true;
    definirMsg("Capturando legendas…");
    const r = await pedir("gerar");
    b.disabled = false;
    if (!r || r.ok === false) {
      definirMsg(r && r.erro ? r.erro : "Não consegui iniciar.", "erro");
      return;
    }
    if (r.estado === "ja_gerado") {
      definirMsg(r.mensagem || "Já geradas.", "ok");
      return;
    }
    definirMsg(r.estado === "pedindo_legenda" ? "Lendo o CC do vídeo…" : "Enviado para o daemon.", "ok");
    agendar();
    setTimeout(recentes, 8000);
  });

  $("gerarTodas").addEventListener("click", async () => {
    const b = $("gerarTodas");
    b.disabled = true;
    const r = await pedir("gerar_todas");
    b.disabled = false;
    if (!r || !r.ok) {
      definirMsg("Não consegui falar com as abas. Recarregue as páginas das aulas.", "erro");
      return;
    }
    definirMsg(
      r.abas
        ? `Pedindo legendas em ${r.abas} aba(s). As notas aparecem aos poucos.`
        : "Nenhuma aba de aula reconhecida. Abra a página da aula e recarregue.",
      r.abas ? "ok" : "erro"
    );
    agendar();
  });

  $("gerarLink").addEventListener("click", async () => {
    const url = $("link").value.trim();
    if (!url) {
      definirMsg("Cole um link do YouTube.", "erro");
      return;
    }
    const b = $("gerarLink");
    b.disabled = true;
    const r = await pedir("gerar_url", { url });
    b.disabled = false;
    if (!r || r.ok === false) {
      definirMsg(r && r.erro ? r.erro : "Não consegui processar o link.", "erro");
      return;
    }
    definirMsg(
      r.estado === "abrindo_video"
        ? "Abrindo o vídeo para ler o CC…"
        : r.estado === "em_andamento"
        ? "Já estou processando este vídeo."
        : "Enviado para o daemon.",
      "ok"
    );
    agendar();
    setTimeout(recentes, 8000);
  });

  $("auto").addEventListener("change", async (e) => {
    await pedir("config", { cfg: { auto: e.target.checked } });
    definirMsg(e.target.checked ? "Automático ativado." : "Automático desativado.", "ok");
  });

  $("autoYoutube").addEventListener("change", async (e) => {
    await pedir("config", { cfg: { autoYoutube: e.target.checked } });
    definirMsg(
      e.target.checked
        ? "Também gera notas quando você abre vídeos direto no YouTube."
        : "Só gera dentro das páginas de aula.",
      "ok"
    );
  });

  $("video").addEventListener("click", () => {
    if (ultimoCaminho) {
      navigator.clipboard.writeText(ultimoCaminho);
      definirMsg("Caminho copiado.", "ok");
    }
  });
}

window.addEventListener("unload", () => clearTimeout(timer));
iniciar();
