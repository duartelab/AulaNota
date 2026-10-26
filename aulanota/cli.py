from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import config, notes, ollama, pipeline, server
from .store import Banco

VERSAO = server.VERSAO


def _cfg(args) -> config.Config:
    caminho = Path(args.regras).expanduser() if getattr(args, "regras", None) else None
    cfg = config.carregar(caminho)
    if getattr(args, "vault", None):
        cfg.vault = Path(args.vault).expanduser().resolve()
        cfg.vault.mkdir(parents=True, exist_ok=True)
    return cfg


def _info_youtube(exe: str, url: str, referer: str | None, cookies: str | None) -> dict:
    cmd = [exe, "--dump-single-json", "--skip-download", "--no-warnings", "--no-playlist", url]
    if referer:
        cmd[1:1] = ["--referer", referer]
    if cookies:
        cmd[1:1] = ["--cookies-from-browser", cookies]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
    except Exception:
        pass
    return {}


def _baixar_legenda(
    exe: str, url: str, referer: str | None, cookies: str | None
) -> tuple[str, Path]:
    tmp = Path(tempfile.mkdtemp(prefix="aulanota-legenda-"))
    cmd = [
        exe,
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        "pt.*,pt,en.*,en",
        "--sub-format",
        "vtt",
        "--no-warnings",
        "--no-playlist",
        "-o",
        str(tmp / "%(id)s.%(ext)s"),
    ]
    if referer:
        cmd[1:1] = ["--referer", referer]
    if cookies:
        cmd[1:1] = ["--cookies-from-browser", cookies]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    arquivos = sorted(tmp.glob("*.vtt"))
    if not arquivos:
        dica = (
            "Não encontrei legenda pública. Se o vídeo é privado/restrito, use a extensão "
            "no navegador (ela lê o CC usando a sua sessão, sem baixar o vídeo)."
        )
        erro = (r.stderr or r.stdout or "").strip()[-500:]
        raise SystemExit(f"{dica}\nDetalhe do yt-dlp: {erro}")
    return arquivos[0].read_text(encoding="utf-8"), arquivos[0]


def _video_id_da_url(url: str) -> str:
    m = re.search(r"(?:[?&]v=|youtu\.be/|/embed/|/shorts/|/live/)([A-Za-z0-9_-]{6,})", url or "")
    return m.group(1) if m else ""


def cmd_add(args) -> int:
    cfg = _cfg(args)
    url = args.url
    pagina = args.pagina or ""
    dados: dict = {
        "pagina_url": pagina,
        "pagina_titulo": args.pagina_titulo or "",
        "video_titulo": args.titulo or "",
        "canal": "",
        "video_id": _video_id_da_url(url),
    }

    if args.legenda:
        texto = Path(args.legenda).expanduser().read_text(encoding="utf-8")
    else:
        exe = config.localizar_ytdlp()
        if not exe:
            raise SystemExit(
                "yt-dlp não encontrado. Rode ./instalar.sh ou use a extensão no navegador."
            )
        info = _info_youtube(exe, url, pagina or None, args.cookies)
        dados.update(
            {
                "video_id": info.get("id", ""),
                "video_titulo": dados["video_titulo"] or info.get("title", ""),
                "canal": info.get("uploader") or info.get("channel") or "",
                "pagina_url": pagina or info.get("webpage_url", ""),
            }
        )
        texto, arq = _baixar_legenda(exe, url, pagina or None, args.cookies)
        if not dados["video_id"]:
            m = re.match(r"([\w-]{6,})", arq.stem)
            dados["video_id"] = m.group(1) if m else ""
        print(f"[aulanota] legenda obtida: {arq.name} ({len(texto)} bytes)")

    dados["legenda"] = {"formato": "vtt", "conteudo": texto}
    resultado = pipeline.processar(
        cfg, dados, forcado=args.disciplina, sobrescrever=args.sobrescrever
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if resultado.get("estado") in ("pronto", "ja_existe") else 1


def cmd_lote(args) -> int:
    cfg = _cfg(args)
    arquivo = Path(args.arquivo).expanduser()
    if not arquivo.exists():
        raise SystemExit(f"Arquivo não encontrado: {arquivo}")
    linhas = [
        l.strip()
        for l in arquivo.read_text(encoding="utf-8").splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]
    if not linhas:
        raise SystemExit("O arquivo está vazio.")

    total = ok = 0
    for i, linha in enumerate(linhas, 1):
        partes = linha.split()
        url = partes[0]
        pagina = args.pagina or (partes[1] if len(partes) > 1 else "")
        disciplina = args.disciplina or (partes[2] if len(partes) > 2 else None)
        print(f"\n[{i}/{len(linhas)}] {url}")
        total += 1
        ns = argparse.Namespace(
            url=url,
            pagina=pagina,
            pagina_titulo=args.pagina_titulo,
            titulo="",
            disciplina=disciplina,
            legenda=None,
            sobrescrever=args.sobrescrever,
            cookies=args.cookies,
            regras=args.regras,
            vault=args.vault,
        )
        try:
            cmd_add(ns)
            ok += 1
        except SystemExit as e:
            print(f"  falhou: {e}")
        except Exception as e:
            print(f"  falhou: {e}")
        if i < len(linhas) and args.atraso > 0:
            time.sleep(args.atraso)
    print(f"\nConcluído: {ok}/{total}.")
    return 0 if ok else 1


def cmd_serve(args) -> int:
    server.servir(_cfg(args))
    return 0


def cmd_doctor(args) -> int:
    cfg = _cfg(args)
    problemas = []

    print(f"AulaNota {VERSAO}")
    print(f"Python           {sys.version.split()[0]}")
    print(f"Vault            {cfg.vault} {'(ok)' if cfg.vault.exists() else '(criando)'}")
    try:
        con = sqlite3.connect(":memory:")
        con.execute("create virtual table t using fts5(x)")
        print(f"SQLite FTS5      ok ({sqlite3.sqlite_version})")
    except Exception as e:
        problemas.append(f"SQLite sem FTS5: {e}")

    ok, modelos = ollama.vivo(cfg)
    print(f"Ollama           {'online' if ok else 'OFFLINE'} em {cfg.ollama_url}")
    if ok:
        print(f"Modelo           {cfg.modelo} {'disponível' if cfg.modelo in modelos else 'NÃO baixado'}")
        if cfg.modelo not in modelos:
            problemas.append(f"Baixe o modelo: ollama pull {cfg.modelo}")
    else:
        problemas.append("Inicie o Ollama: systemctl --user start ollama")

    exe = config.localizar_ytdlp()
    print(f"yt-dlp           {exe or 'não encontrado (só extensão funcionará)'}")

    try:
        with socket.create_connection((cfg.host, cfg.porta), timeout=1):
            print(f"Daemon           online em {cfg.host}:{cfg.porta}")
    except OSError:
        print(f"Daemon           offline em {cfg.host}:{cfg.porta} (normal se não iniciou)")

    banco = Banco(cfg)
    try:
        print(f"Notas indexadas  {banco.total()}")
    finally:
        banco.fechar()

    if problemas:
        print("\nPendências:")
        for p in problemas:
            print(f" - {p}")
        return 1
    print("\nTudo pronto.")
    return 0


def cmd_listar(args) -> int:
    cfg = _cfg(args)
    banco = Banco(cfg)
    try:
        for n in banco.recentes(args.limite):
            print(f"{n['data']}  {n['disciplina']:<14} {n['titulo'][:70]}")
            print(f"        {n['caminho']}")
    finally:
        banco.fechar()
    return 0


def cmd_buscar(args) -> int:
    cfg = _cfg(args)
    banco = Banco(cfg)
    try:
        achados = banco.buscar(args.termo, args.limite)
    finally:
        banco.fechar()
    if not achados:
        print("Nada encontrado.")
        return 1
    for n in achados:
        print(f"\n{n['data']}  {n['disciplina']}  {n['titulo']}")
        print(f"  {n['caminho']}")
        print(f"  {n['trecho']}")
    return 0


def cmd_indice(args) -> int:
    cfg = _cfg(args)
    for pasta in sorted(p for p in cfg.vault.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
        if any(pasta.glob("*.md")):
            print(notes.atualizar_indice(pasta))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="aulanota",
        description="Notas de aula locais a partir das legendas do YouTube. Sem gravação.",
    )
    p.add_argument("--regras", help="caminho do regras.toml")
    p.add_argument("--vault", help="pasta do vault (sobrepõe o regras.toml)")
    p.add_argument("--versao", action="version", version=VERSAO)
    sub = p.add_subparsers(dest="cmd")

    ps = sub.add_parser("serve", help="inicia o daemon local (extensão usa este)")
    ps.set_defaults(func=cmd_serve)

    pa = sub.add_parser("add", help="gera notas de um vídeo do YouTube")
    pa.add_argument("url", help="URL do vídeo do YouTube")
    pa.add_argument("--pagina", help="URL da página da aula (disciplina/AVA) para identificar a matéria")
    pa.add_argument("--pagina-titulo", help="título da página da aula")
    pa.add_argument("--titulo", help="título do vídeo (se não vier do yt-dlp)")
    pa.add_argument("--disciplina", help="força o id da disciplina, ex: CALC1")
    pa.add_argument("--legenda", help="usa um arquivo .vtt local em vez de baixar")
    pa.add_argument("--sobrescrever", action="store_true")
    pa.add_argument(
        "--cookies-from-browser",
        dest="cookies",
        help="usa cookies do navegador para vídeos restritos (ex: firefox, chrome)",
    )
    pa.set_defaults(func=cmd_add)

    pt = sub.add_parser(
        "lote",
        help="processa uma lista de URLs (uma por linha: url [pagina] [disciplina])",
    )
    pt.add_argument("arquivo", help="arquivo .txt com uma aula por linha")
    pt.add_argument("--pagina", help="mesma página de aula para todas as linhas")
    pt.add_argument("--pagina-titulo", default="")
    pt.add_argument("--disciplina", help="mesma disciplina para todas as linhas")
    pt.add_argument("--cookies-from-browser", dest="cookies")
    pt.add_argument("--sobrescrever", action="store_true")
    pt.add_argument("--atraso", type=float, default=2.0, help="segundos entre vídeos")
    pt.set_defaults(func=cmd_lote)

    pd = sub.add_parser("doctor", help="diagnóstico do ambiente")
    pd.set_defaults(func=cmd_doctor)

    pl = sub.add_parser("listar", help="últimas notas")
    pl.add_argument("--limite", type=int, default=20)
    pl.set_defaults(func=cmd_listar)

    pb = sub.add_parser("buscar", help="busca no índice (FTS5)")
    pb.add_argument("termo")
    pb.add_argument("--limite", type=int, default=20)
    pb.set_defaults(func=cmd_buscar)

    pi = sub.add_parser("indice", help="regenera _indice.md de cada disciplina")
    pi.set_defaults(func=cmd_indice)

    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help()
        return 0
    return args.func(args)
