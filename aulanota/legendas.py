from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from .config import Config, localizar_ytdlp


class ErroLegenda(RuntimeError):
    pass


def id_de_url(url: str) -> str:
    m = re.search(
        r"(?:[?&]v=|youtu\.be/|/embed/|/shorts/|/live/)([A-Za-z0-9_-]{11})", url or ""
    )
    return m.group(1) if m else ""


def _comum(exe: str, cookies: str | None, referer: str | None) -> list[str]:
    cmd = [exe]
    if cookies:
        cmd += ["--cookies-from-browser", cookies]
    if referer:
        cmd += ["--referer", referer]
    return cmd


def _info(exe: str, url: str, cookies: str | None, referer: str | None) -> dict:
    import json

    cmd = _comum(exe, cookies, referer) + [
        "--dump-single-json",
        "--skip-download",
        "--no-warnings",
        "--no-playlist",
        url,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
    except Exception:
        pass
    return {}


def _baixar(
    exe: str, url: str, cookies: str | None, referer: str | None
) -> tuple[str, Path]:
    tmp = Path(tempfile.mkdtemp(prefix="aulanota-legenda-"))
    cmd = _comum(exe, cookies, referer) + [
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
        url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    arquivos = sorted(tmp.glob("*.vtt"))
    if not arquivos:
        detalhe = (r.stderr or r.stdout or "").strip().replace("\n", " ")[-300:]
        raise ErroLegenda(detalhe or "sem legendas disponíveis")
    return arquivos[0].read_text(encoding="utf-8", errors="replace"), arquivos[0]


def obter(
    cfg: Config, url: str, pagina_url: str | None = None, video_id: str = ""
) -> tuple[str, dict, str]:
    """Baixa a legenda do YouTube via yt-dlp. Retorna (vtt, info, modo_cookies)."""
    exe = localizar_ytdlp()
    if not exe:
        raise ErroLegenda("yt-dlp não encontrado. Rode ./instalar.sh")

    if cfg.cookies:
        tentativas: list[str | None] = [cfg.cookies]
    else:
        tentativas = [None, "firefox", "chrome", "chromium", "brave"]

    erros: list[str] = []
    for cookies in tentativas:
        try:
            info = _info(exe, url, cookies, pagina_url)
            texto, arq = _baixar(exe, url, cookies, pagina_url)
            if not video_id:
                video_id = str(info.get("id") or "")
            info["id"] = info.get("id") or video_id
            info["_arquivo"] = str(arq)
            return texto, info, cookies or "sem cookies"
        except ErroLegenda as exc:
            erros.append(f"{cookies or 'sem cookies'}: {exc}")
        except Exception as exc:  # pragma: no cover
            erros.append(f"{cookies or 'sem cookies'}: {exc}")

    raise ErroLegenda(
        "Não consegui obter a legenda deste vídeo. "
        "Se ele for privado, defina em regras.toml: [legendas] cookies = \"firefox\" "
        "(ou chrome). Detalhes: " + " | ".join(erros[-2:])
    )
