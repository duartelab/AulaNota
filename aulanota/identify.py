from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

from .config import Config, Disciplina


@dataclass
class Identificacao:
    disciplina: Disciplina
    origem: str


def slug(texto: str, limite: int = 40) -> str:
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t[:limite].strip("-") or "geral"


def _hash(texto: str, n: int = 4) -> str:
    return hashlib.sha1((texto or "").encode("utf-8")).hexdigest()[:n]


def limpar_titulo(titulo: str) -> str:
    if not titulo:
        return ""
    t = re.sub(r"\s*[\|\-–—]\s*(YouTube|Udemy|Alura|Hotmart|Moodle|AVA|Sala Virtual).*$", "", titulo, flags=re.I)
    t = re.sub(r"^(Curso|Course|Aula|Videoaula)\s*[:\-–—]\s*", "", t, flags=re.I)
    t = re.sub(r"\s{2,}", " ", t).strip(" -–—|")
    return t


def _primeiras_palavras(texto: str, n: int = 4) -> str:
    partes = [p for p in re.split(r"\s+", texto or "") if p]
    return " ".join(partes[:n]).strip()


def identificar(
    cfg: Config,
    pagina_url: str,
    pagina_titulo: str,
    video_titulo: str,
    forcado: str | None = None,
) -> Identificacao:
    if forcado:
        for d in cfg.disciplinas:
            if d.id.lower() == forcado.lower():
                return Identificacao(d, "manual")
        return Identificacao(Disciplina(id=forcado, nome=forcado), "manual")

    alvo = f"{pagina_url or ''} {pagina_titulo or ''} {video_titulo or ''}"
    for d in cfg.disciplinas:
        for padrao in d.padroes:
            try:
                if re.search(padrao, alvo, re.I):
                    return Identificacao(d, "regra")
            except re.error:
                continue

    url = pagina_url or ""
    titulo = limpar_titulo(pagina_titulo) or limpar_titulo(video_titulo)
    ident = ""
    nome = titulo

    if m := re.search(r"udemy\.com/course/([^/?#]+)", url, re.I):
        ident = "UD-" + slug(m.group(1), 24).upper()
        if not nome:
            nome = m.group(1).replace("-", " ").title()
    elif m := re.search(r"alura\.com\.br/(?:cursos|formacao)/([^/?#]+)", url, re.I):
        ident = "AL-" + slug(m.group(1), 24).upper()
        if not nome:
            nome = m.group(1).replace("-", " ").title()
    elif m := re.search(r"/course/view\.php\?id=(\d+)", url, re.I):
        ident = "M" + m.group(1)
    elif m := re.search(r"club\.hotmart\.com/(?:[^/?#]+/)?([^/?#]+)", url, re.I):
        ident = "HM-" + slug(m.group(1), 24).upper()
        if not nome:
            nome = m.group(1).replace("-", " ").title()
    else:
        base = _primeiras_palavras(titulo or video_titulo, 4)
        ident = "G-" + slug(base, 20).upper() + "-" + _hash(alvo, 4).upper()
        nome = base or "Geral"

    if not nome:
        nome = ident
    return Identificacao(Disciplina(id=re.sub(r"[^A-Za-z0-9_-]", "", ident), nome=nome), "auto")


def id_aula(video_id: str, video_titulo: str) -> str:
    if video_id:
        return video_id
    return _hash(f"{video_titulo}{_hash(video_titulo, 6)}", 8)
