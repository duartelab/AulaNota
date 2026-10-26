from __future__ import annotations

import json
import queue
import time
from datetime import datetime
import threading
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import ollama, pipeline
from .config import Config
from .store import Banco

VERSAO = "0.1.0"


class Fila:
    """Fila persistente: sobrevive a reinícios do daemon e retoma o que faltou."""

    HISTORICO_DIAS = 7

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.q: queue.Queue = queue.Queue()
        self.trabalhos: dict[str, dict] = {}
        self.trava = threading.Lock()
        self.pasta = cfg.pasta_estado / "fila"
        self.pasta.mkdir(parents=True, exist_ok=True)
        self._carregar()
        threading.Thread(target=self._worker, daemon=True).start()

    def _arquivo(self, jid: str):
        return self.pasta / f"{jid}.json"

    def _persistir(self, jid: str) -> None:
        dados = self.trabalhos.get(jid)
        if not dados:
            return
        arq = self._arquivo(jid)
        tmp = arq.with_suffix(".tmp")
        tmp.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        tmp.replace(arq)

    def _carregar(self) -> None:
        agora = time.time()
        retomados = 0
        for arq in sorted(self.pasta.glob("*.json")):
            try:
                d = json.loads(arq.read_text(encoding="utf-8"))
                jid = d["id"]
                dados = d["dados"]
            except Exception:
                arq.unlink(missing_ok=True)
                continue
            if d.get("estado") in ("na_fila", "processando"):
                d["estado"] = "na_fila"
                d["progresso"] = {"etapa": "retomado após reinício", "parte": 0, "total": 0}
                self.trabalhos[jid] = d
                self.q.put((jid, dados, d.get("forcado"), bool(d.get("sobrescrever"))))
                retomados += 1
            elif agora - float(d.get("criado_ts") or 0) <= self.HISTORICO_DIAS * 86400:
                self.trabalhos[jid] = d
            else:
                arq.unlink(missing_ok=True)
        if retomados:
            print(f"[aulanota] {retomados} trabalho(s) retomado(s) após reinício", flush=True)

    def enviar(self, dados: dict, forcado: str | None, sobrescrever: bool) -> dict:
        jid = uuid.uuid4().hex[:12]
        agora = time.time()
        with self.trava:
            self.trabalhos[jid] = {
                "id": jid,
                "estado": "na_fila",
                "video_id": str(dados.get("video_id") or ""),
                "video_titulo": str(dados.get("video_titulo") or ""),
                "pagina_titulo": str(dados.get("pagina_titulo") or ""),
                "criado_ts": agora,
                "criado_em": datetime.now().isoformat(timespec="seconds"),
                "dados": dados,
                "forcado": forcado,
                "sobrescrever": bool(sobrescrever),
            }
            self._persistir(jid)
            publico = self._publico(self.trabalhos[jid])
        self.q.put((jid, dados, forcado, sobrescrever))
        print(f"[aulanota] trabalho {jid} na fila: {dados.get('video_titulo') or dados.get('video_id')}", flush=True)
        return publico

    @staticmethod
    def _publico(d: dict) -> dict:
        return {k: v for k, v in d.items() if k not in ("dados", "forcado", "sobrescrever")}

    def consultar(self, jid: str) -> dict | None:
        with self.trava:
            d = self.trabalhos.get(jid)
            return self._publico(d) if d else None

    def listar(self, limite: int = 20) -> list[dict]:
        with self.trava:
            itens = sorted(
                self.trabalhos.values(), key=lambda x: x.get("criado_ts", 0), reverse=True
            )
            return [self._publico(d) for d in itens[:limite]]

    def resumo(self) -> dict:
        with self.trava:
            pendentes = sum(
                1 for d in self.trabalhos.values() if d.get("estado") in ("na_fila", "processando")
            )
            return {"pendentes": pendentes, "historico": len(self.trabalhos)}

    def _atualizar(self, jid: str, **campos) -> None:
        with self.trava:
            if jid in self.trabalhos:
                self.trabalhos[jid].update(campos)
                self._persistir(jid)

    def _worker(self) -> None:
        while True:
            jid, dados, forcado, sobrescrever = self.q.get()
            self._atualizar(
                jid, estado="processando", erro=None,
                progresso={"etapa": "iniciando", "parte": 0, "total": 0},
            )
            try:
                def prog(etapa, i=None, n=None):
                    self._atualizar(jid, progresso={"etapa": etapa, "parte": i, "total": n})

                resultado = pipeline.processar(
                    self.cfg, dados, forcado=forcado,
                    sobrescrever=sobrescrever, progresso=prog,
                )
                self._atualizar(
                    jid, estado=resultado.get("estado", "pronto"),
                    resultado=resultado, concluido_em=datetime.now().isoformat(timespec="seconds"),
                )
                print(f"[aulanota] {jid} ok -> {resultado.get('caminho', '')}", flush=True)
            except Exception as exc:
                print(f"[aulanota] {jid} erro: {exc}", flush=True)
                traceback.print_exc()
                self._atualizar(
                    jid, estado="erro", erro=str(exc),
                    concluido_em=datetime.now().isoformat(timespec="seconds"),
                )
            finally:
                self.q.task_done()


class Handler(BaseHTTPRequestHandler):
    cfg: Config
    fila: Fila
    server_version = f"AulaNota/{VERSAO}"

    def log_message(self, fmt, *args):
        print(f"[aulanota] {self.address_string()} {fmt % args}", flush=True)

    def _cabecalhos(self, codigo: int, tipo: str | None = None, tamanho: int | None = None):
        self.send_response(codigo)
        if tipo:
            self.send_header("Content-Type", tipo)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Cache-Control", "no-store")
        if tamanho is not None:
            self.send_header("Content-Length", str(tamanho))
        self.end_headers()

    def _json(self, codigo: int, obj):
        corpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._cabecalhos(codigo, "application/json; charset=utf-8", len(corpo))
        self.wfile.write(corpo)

    def do_OPTIONS(self):
        self._cabecalhos(204)

    def do_GET(self):
        url = urlparse(self.path)
        qs = parse_qs(url.query)

        if url.path in ("/health", "/"):
            ok, modelos = ollama.vivo(self.cfg)
            banco = Banco(self.cfg)
            try:
                total = banco.total()
            finally:
                banco.fechar()
            return self._json(
                200,
                {
                    "ok": True,
                    "versao": VERSAO,
                    "vault": str(self.cfg.vault),
                    "ollama": ok,
                    "modelo_configurado": self.cfg.modelo,
                    "modelo_disponivel": self.cfg.modelo in modelos,
                    "modelos": modelos,
                    "notas_indexadas": total,
                    "fila": self.fila.resumo(),
                },
            )

        if url.path == "/jobs":
            limite = int((qs.get("limite") or ["20"])[0])
            return self._json(200, {"jobs": self.fila.listar(limite)})

        if url.path.startswith("/jobs/"):
            jid = url.path.rsplit("/", 1)[-1]
            job = self.fila.consultar(jid)
            if not job:
                return self._json(404, {"erro": "trabalho não encontrado"})
            return self._json(200, job)

        if url.path == "/recentes":
            limite = int((qs.get("limite") or ["20"])[0])
            banco = Banco(self.cfg)
            try:
                return self._json(200, {"notas": banco.recentes(limite)})
            finally:
                banco.fechar()

        if url.path == "/busca":
            termo = (qs.get("q") or [""])[0].strip()
            if not termo:
                return self._json(400, {"erro": "informe ?q="})
            banco = Banco(self.cfg)
            try:
                return self._json(200, {"termo": termo, "notas": banco.buscar(termo)})
            finally:
                banco.fechar()

        return self._json(404, {"erro": "rota não encontrada"})

    def do_POST(self):
        url = urlparse(self.path)
        if url.path not in ("/notas", "/gerar"):
            return self._json(404, {"erro": "rota não encontrada"})
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
            if tamanho <= 0 or tamanho > 25 * 1024 * 1024:
                return self._json(400, {"erro": "corpo inválido ou grande demais"})
            dados = json.loads(self.rfile.read(tamanho).decode("utf-8"))
            if not isinstance(dados, dict):
                raise ValueError
        except Exception:
            return self._json(400, {"erro": "JSON inválido"})

        forcado = dados.pop("disciplina", None) or None
        sobrescrever = bool(dados.pop("sobrescrever", False))
        job = self.fila.enviar(dados, forcado, sobrescrever)
        return self._json(
            202,
            {
                "job": job["id"],
                "estado": job["estado"],
                "consulte": f"/jobs/{job['id']}",
            },
        )


def servir(cfg: Config) -> None:
    Handler.cfg = cfg
    Handler.fila = Fila(cfg)
    httpd = ThreadingHTTPServer((cfg.host, cfg.porta), Handler)
    print(
        f"[aulanota] daemon em http://{cfg.host}:{cfg.porta} · vault: {cfg.vault}",
        flush=True,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[aulanota] encerrando", flush=True)
    finally:
        httpd.server_close()
