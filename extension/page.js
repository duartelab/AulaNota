/* Roda na página da aula (AVA, Udemy, Alura, Hotmart...) e informa
   URL, título e os IDs de vídeos do YouTube encontrados — inclusive
   players institucionais que embrulham o YouTube (ex.: youtube-embed.html?v=ID).
   Não lê áudio nem vídeo. */
(() => {
  const host = location.hostname;
  if (/(^|\.)youtube\.com$|(^|\.)youtube-nocookie\.com$|(^|\.)youtu\.be$/.test(host)) return;

  const RE_EMBED = /(?:youtube(?:-nocookie)?\.com\/(?:embed|live|shorts)\/|youtu\.be\/)([A-Za-z0-9_-]{11})/gi;
  const RE_QUERY = /(?:youtube(?:-nocookie)?\.com\/watch|youtube-embed\.html)[^"'<>\\\s]{0,160}?[?&]v=([A-Za-z0-9_-]{11})/gi;
  const RE_SRC = /[?&]v=([A-Za-z0-9_-]{11})/g;

  function extrair(texto, ids) {
    const t = String(texto || "");
    if (!t) return;
    for (const re of [RE_EMBED, RE_QUERY]) {
      re.lastIndex = 0;
      let m;
      while ((m = re.exec(t))) ids.add(m[1]);
    }
    if (/youtube|youtu\.be/i.test(t)) {
      RE_SRC.lastIndex = 0;
      let m;
      while ((m = RE_SRC.exec(t))) {
        if (m.index > 0 && t[m.index - 1] === "/") continue;
        ids.add(m[1]);
      }
    }
  }

  let varreuHtml = false;

  function embeds() {
    const ids = new Set();
    extrair(location.href, ids);

    const iframes = [...document.querySelectorAll("iframe")];
    for (const f of iframes) {
      if (/youtube-embed\.html/i.test(f.src || "")) extrair(f.src, ids);
    }
    iframes.sort((a, b) => {
      const area = (x) => (x.offsetWidth || 0) * (x.offsetHeight || 0);
      return area(b) - area(a);
    });
    for (const f of iframes) {
      for (const attr of ["src", "data-src", "data-lazy-src", "data-original", "srcdoc"]) {
        extrair(f.getAttribute(attr), ids);
      }
    }
    for (const a of document.querySelectorAll("a[href]")) extrair(a.href, ids);
    for (const el of document.querySelectorAll("[data-video], [data-video-id], [data-youtube]")) {
      extrair(el.getAttribute("data-video"), ids);
      extrair(el.getAttribute("data-video-id"), ids);
      extrair(el.getAttribute("data-youtube"), ids);
    }
    if (!varreuHtml) {
      varreuHtml = true;
      try {
        const html = (document.documentElement && document.documentElement.innerHTML) || "";
        extrair(html.slice(0, 2000000), ids);
      } catch (e) {}
    }
    return [...ids];
  }

  function enviar() {
    try {
      chrome.runtime.sendMessage({
        tipo: "pagina",
        url: location.href,
        titulo: document.title,
        embeds: embeds()
      });
    } catch (e) {}
  }

  chrome.runtime.onMessage.addListener((msg, _r, responder) => {
    if (msg && msg.tipo === "pedir_legendas") {
      for (const f of document.querySelectorAll("iframe")) {
        if (/(youtube\.com|youtube-nocookie\.com)\/embed\//.test(f.src || "")) {
          try { f.contentWindow.postMessage({ __aulanota_pedido: true, motivo: "popup" }, "*"); } catch (e) {}
        }
      }
      enviar();
      responder({ ok: true });
    }
    return true;
  });

  enviar();
  let t = null;
  const obs = new MutationObserver(() => {
    clearTimeout(t);
    t = setTimeout(enviar, 1200);
  });
  obs.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("popstate", enviar);
  window.addEventListener("hashchange", enviar);
})();
