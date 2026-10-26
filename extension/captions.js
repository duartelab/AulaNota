/* Ponte entre o script que roda no mundo da página do YouTube e a extensão. */
(() => {
  const recebeu = { valor: false };

  window.addEventListener("message", (e) => {
    if (e.source !== window || !e.data || !e.data.__aulanota) return;
    recebeu.valor = true;
    const { __aulanota, ...resto } = e.data;
    if (resto.tipo === "legendas" || resto.tipo === "sem_legenda") {
      try { chrome.runtime.sendMessage(resto); } catch (err) {}
    }
  });

  chrome.runtime.onMessage.addListener((msg, _remetente, responder) => {
    if (msg && msg.tipo === "pedir_legendas") {
      window.postMessage({ __aulanota_pedido: true, motivo: "popup" }, "*");
      responder({ ok: true });
    }
    return true;
  });

  /* Firefox antigo/ambiente sem content_scripts "world: MAIN": injeta via tag. */
  setTimeout(() => {
    if (recebeu.valor) return;
    try {
      const s = document.createElement("script");
      s.src = chrome.runtime.getURL("injetar.js");
      s.onload = () => s.remove();
      (document.head || document.documentElement).appendChild(s);
    } catch (e) {}
  }, 2500);

  window.postMessage({ __aulanota_pedido: true, motivo: "carregamento" }, "*");
})();
