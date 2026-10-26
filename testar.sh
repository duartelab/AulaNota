#!/usr/bin/env bash
# Verifica de ponta a ponta que a nota é gerada, salva em disco e indexada.
# Uso: ./testar.sh            (teste normal)
#      ./testar.sh reinicio   (derruba o daemon no meio e confirma a retomada)
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="http://127.0.0.1:8790"
MODO="${1:-normal}"

echo "== AulaNota · teste de salvamento =="

if ! curl -sf --max-time 4 "$BASE/health" >/dev/null; then
  echo "ERRO: daemon offline. Rode: systemctl --user start aulanota"
  exit 1
fi

python3 - "$RAIZ/exemplos/teste-rapido.vtt" > /tmp/aulanota-teste.json <<'PY'
import json, sys
vtt = open(sys.argv[1], encoding="utf-8").read()
print(json.dumps({
    "video_id": "TESTE-AULANOTA",
    "video_titulo": "Teste de salvamento",
    "pagina_url": "https://exemplo.local/teste",
    "pagina_titulo": "Página de teste",
    "disciplina": "TESTE",
    "sobrescrever": True,
    "legenda": {"formato": "vtt", "conteudo": vtt},
}, ensure_ascii=False))
PY

echo "1) enviando legenda de teste para o daemon..."
JOB=$(curl -sf --max-time 20 -X POST "$BASE/notas" \
  -H 'Content-Type: application/json' --data-binary @/tmp/aulanota-teste.json \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['job'])")
echo "   job: $JOB"

if [ "$MODO" = "reinicio" ]; then
  echo "2) reiniciando o daemon no meio do trabalho (teste de retomada)..."
  sleep 2
  systemctl --user restart aulanota
  sleep 2
else
  echo "2) aguardando o processamento (pode levar ~1 min)..."
fi

ESTADO=""
for i in $(seq 1 120); do
  sleep 3
  RESP=$(curl -sf --max-time 5 "$BASE/jobs/$JOB" 2>/dev/null || echo '{}')
  ESTADO=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('estado',''))" 2>/dev/null || true)
  ETAPA=$(echo "$RESP" | python3 -c "import sys,json;d=json.load(sys.stdin);print((d.get('progresso') or {}).get('etapa',''))" 2>/dev/null || true)
  printf "   [%3ss] %s %s\n" "$((i*3))" "$ESTADO" "$ETAPA"
  case "$ESTADO" in
    pronto|ja_existe|erro) break ;;
  esac
done

echo
if [ "$ESTADO" = "erro" ]; then
  echo "FALHOU. Resposta do daemon:"
  echo "$RESP" | python3 -m json.tool
  exit 1
fi

CAMINHO=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('resultado',{}).get('caminho',''))")
echo "3) nota relatada: ${CAMINHO:-<vazio>}"
[ -n "$CAMINHO" ] && [ -f "$CAMINHO" ] || { echo "FALHOU: arquivo não existe."; exit 1; }

echo "4) conferindo conteúdo, índice e banco..."
grep -q "Teste de salvamento" "$CAMINHO" || { echo "FALHOU: título ausente."; exit 1; }
grep -q "## Resumo" "$CAMINHO" || { echo "FALHOU: seção Resumo ausente."; exit 1; }
[ -f "$(dirname "$CAMINHO")/_indice.md" ] || { echo "FALHOU: _indice.md ausente."; exit 1; }

python3 - "$CAMINHO" <<'PY'
import sqlite3, sys, pathlib
caminho = sys.argv[1]
db = pathlib.Path.home() / "Estudos/.aulanota/notas.db"
c = sqlite3.connect(db)
n = c.execute("select count(*) from notas where caminho=?", (caminho,)).fetchone()[0]
print(f"   banco: {n} registro(s) para este arquivo")
sys.exit(0 if n == 1 else 1)
PY

echo
echo "SALVAMENTO OK"
echo "   arquivo: $CAMINHO"
echo "   abra a pasta com: xdg-open \"$(dirname "$CAMINHO")\""
echo "   (esta nota é só um teste; apague a pasta TESTE quando quiser)"
