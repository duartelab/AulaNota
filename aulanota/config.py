from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_REGRAS = RAIZ / "regras.toml"


@dataclass
class Disciplina:
    id: str
    nome: str
    padroes: list[str] = field(default_factory=list)


@dataclass
class Config:
    vault: Path
    host: str
    porta: int
    ollama_url: str
    modelo: str
    num_ctx: int
    temperatura: float
    idioma: str
    incluir_transcricao: bool
    max_palavras_chunk: int
    sobreposicao_palavras: int
    cookies: str
    disciplinas: list[Disciplina]

    @property
    def pasta_estado(self) -> Path:
        return self.vault / ".aulanota"

    @property
    def banco(self) -> Path:
        return self.pasta_estado / "notas.db"


def _expandir(caminho: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(caminho))).resolve()


def carregar(caminho: Path | None = None) -> Config:
    arq = caminho or ARQUIVO_REGRAS
    dados: dict = {}
    if arq.exists():
        with arq.open("rb") as f:
            dados = tomllib.load(f)

    geral = dados.get("geral", {})
    notas = dados.get("notas", {})
    modelo = dados.get("modelo", {})
    servidor = dados.get("servidor", {})
    legendas_cfg = dados.get("legendas", {})

    disciplinas = [
        Disciplina(
            id=str(d.get("id", "")).strip(),
            nome=str(d.get("nome", d.get("id", ""))).strip(),
            padroes=[str(p) for p in d.get("padroes", [])],
        )
        for d in dados.get("disciplina", [])
        if d.get("id")
    ]

    cfg = Config(
        vault=_expandir(geral.get("vault", "~/Estudos")),
        host=servidor.get("host", "127.0.0.1"),
        porta=int(servidor.get("porta", 8790)),
        ollama_url=os.environ.get("AULANOTA_OLLAMA", modelo.get("url", "http://127.0.0.1:11434")),
        modelo=os.environ.get("AULANOTA_MODELO", modelo.get("nome", "qwen3:4b-instruct")),
        num_ctx=int(modelo.get("num_ctx", 4096)),
        temperatura=float(modelo.get("temperatura", 0.2)),
        idioma=geral.get("idioma", "pt-BR"),
        incluir_transcricao=bool(notas.get("incluir_transcricao", False)),
        max_palavras_chunk=int(notas.get("max_palavras_chunk", 900)),
        sobreposicao_palavras=int(notas.get("sobreposicao_palavras", 100)),
        cookies=os.environ.get("AULANOTA_COOKIES", str(legendas_cfg.get("cookies", ""))),
        disciplinas=disciplinas,
    )

    for pasta in (
        cfg.vault,
        cfg.pasta_estado,
        cfg.vault / "_revisar",
        cfg.vault / "_lixo",
    ):
        pasta.mkdir(parents=True, exist_ok=True)

    return cfg


def localizar_ytdlp() -> str | None:
    candidatos = [
        RAIZ / ".venv" / "bin" / "yt-dlp",
        Path("/usr/bin/yt-dlp"),
        Path("/usr/local/bin/yt-dlp"),
        Path(os.path.expanduser("~/.local/bin/yt-dlp")),
    ]
    for c in candidatos:
        if c.exists() and os.access(c, os.X_OK):
            return str(c)
    return None
