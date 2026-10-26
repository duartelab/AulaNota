#!/usr/bin/env bash
# Instala o daemon do AulaNota e prepara a extensão. Não usa sudo.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAVEGADOR="${1:-chrome}"

echo "== AulaNota =="
echo "pasta: $RAIZ"
echo

echo "[1/5] Criando pastas do vault..."
mkdir -p "$HOME/Estudos"/{_revisar,_lixo,.aulanota}
echo "  ok: ~/Estudos"

echo "[2/5] Preparando yt-dlp (opcional, para o comando add)..."
if [ ! -x "$RAIZ/.venv/bin/yt-dlp" ]; then
  python3 -m venv "$RAIZ/.venv" >/dev/null 2>&1 || true
  "$RAIZ/.venv/bin/pip" install --quiet --upgrade pip >/dev/null 2>&1 || true
  "$RAIZ/.venv/bin/pip" install --quiet yt-dlp >/dev/null 2>&1 || echo "  aviso: yt-dlp não instalado (a extensão não depende dele)"
fi
[ -x "$RAIZ/.venv/bin/yt-dlp" ] && echo "  ok: $("$RAIZ/.venv/bin/yt-dlp" --version)"

echo "[3/5] Ativando manifesto da extensão para: $NAVEGADOR"
PAGINA_EXT="chrome://extensions"
case "$NAVEGADOR" in
  firefox)
    cp "$RAIZ/extension/manifest.firefox.json" "$RAIZ/extension/manifest.json"
    PAGINA_EXT="about:debugging#/runtime/this-firefox"
    ;;
  brave)
    cp "$RAIZ/extension/manifest.chrome.json" "$RAIZ/extension/manifest.json"
    PAGINA_EXT="brave://extensions"
    ;;
  edge)
    cp "$RAIZ/extension/manifest.chrome.json" "$RAIZ/extension/manifest.json"
    PAGINA_EXT="edge://extensions"
    ;;
  vivaldi)
    cp "$RAIZ/extension/manifest.chrome.json" "$RAIZ/extension/manifest.json"
    PAGINA_EXT="vivaldi://extensions"
    ;;
  chrome|chromium)
    cp "$RAIZ/extension/manifest.chrome.json" "$RAIZ/extension/manifest.json"
    ;;
  *)
    echo "  uso: ./instalar.sh [chrome|chromium|brave|edge|vivaldi|firefox]"
    exit 1
    ;;
esac
echo "  ok: extension/manifest.json"

echo "[4/5] Instalando serviço systemd de usuário..."
mkdir -p "$HOME/.config/systemd/user"
sed "s|__RAIZ__|$RAIZ|g" "$RAIZ/systemd/aulanota.service.in" > "$HOME/.config/systemd/user/aulanota.service"
systemctl --user daemon-reload
systemctl --user enable --now aulanota.service
sleep 1
systemctl --user --no-pager --lines=3 status aulanota.service || true

echo "[5/5] Atalho de linha de comando..."
mkdir -p "$HOME/.local/bin"
ln -sf "$RAIZ/aulanota.sh" "$HOME/.local/bin/aulanota"
echo "  ok: ~/.local/bin/aulanota"

echo
echo "Pronto. Falta carregar a extensão no navegador:"
if [ "$NAVEGADOR" = "firefox" ]; then
  echo "  1. abra $PAGINA_EXT"
  echo "  2. 'Carregar extensão temporária' e escolha: $RAIZ/extension/manifest.json"
else
  echo "  1. abra $PAGINA_EXT"
  echo "  2. ative 'Modo do desenvolvedor'"
  echo "  3. 'Carregar sem compactação' e escolha a pasta: $RAIZ/extension"
fi
echo
echo "Teste: aulanota doctor"
