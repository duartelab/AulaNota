from __future__ import annotations

from datetime import datetime
from pathlib import Path

from . import legendas, notes, resumo, vtt
from .config import Config
from .identify import id_aula, identificar, limpar_titulo
from .store import Banco


class ErroPipeline(RuntimeError):
    pass


def processar(
    cfg: Config,
    dados: dict,
    *,
    forcado: str | None = None,
    sobrescrever: bool = False,
    progresso=None,
) -> dict:
    legenda = dados.get("legenda") or {}
    texto = ""
    formato = "vtt"
    if isinstance(legenda, dict):
        texto = legenda.get("conteudo") or ""
        formato = legenda.get("formato") or "vtt"
    if not texto:
        texto = dados.get("conteudo") or dados.get("legendas") or ""
        formato = dados.get("formato") or "vtt"
    video_id = str(dados.get("video_id") or "").strip()
    video_url = str(dados.get("video_url") or "").strip()
    if not video_id and video_url:
        video_id = legendas.id_de_url(video_url)
    if video_id and not video_url:
        video_url = f"https://www.youtube.com/watch?v={video_id}"

    pagina_url = str(dados.get("pagina_url") or "").strip()
    pagina_titulo = str(dados.get("pagina_titulo") or "").strip()
    video_titulo = limpar_titulo(str(dados.get("video_titulo") or ""))
    canal = str(dados.get("canal") or "").strip()
    idioma = str(dados.get("idioma") or "").strip()
    auto_legenda = bool(dados.get("auto", dados.get("legenda_automatica", False)))
    origem_legenda = "recebida"

    if not texto.strip():
        if not video_url:
            raise ErroPipeline(
                "Nenhuma legenda recebida e nenhuma URL de vídeo informada."
            )
        if progresso:
            try:
                progresso("baixando legendas do vídeo", 0, 0)
            except Exception:
                pass
        texto, info, modo_cookies = legendas.obter(
            cfg, video_url, pagina_url or None, video_id
        )
        origem_legenda = f"yt-dlp ({modo_cookies})"
        video_id = video_id or str(info.get("id") or "")
        video_titulo = video_titulo or limpar_titulo(str(info.get("title") or ""))
        canal = canal or str(info.get("uploader") or info.get("channel") or "")
        idioma = idioma or str(info.get("language") or "")
        formato = "vtt"

    if not video_id:
        video_id = id_aula("", video_titulo)
    video_titulo = video_titulo or video_id

    if progresso:
        try:
            progresso("lendo legenda", 0, 0)
        except Exception:
            pass
    segmentos = vtt.parse(texto)
    if not segmentos:
        raise ErroPipeline(f"Não consegui interpretar a legenda no formato '{formato}'.")

    ident = identificar(cfg, pagina_url, pagina_titulo, video_titulo, forcado)
    aula = id_aula(video_id, video_titulo)
    data_iso = datetime.now().date().isoformat()
    pasta = cfg.vault / ident.disciplina.id
    caminho = pasta / notes.nome_arquivo(data_iso, aula)

    if caminho.exists() and not sobrescrever:
        return {
            "estado": "ja_existe",
            "caminho": str(caminho),
            "disciplina": ident.disciplina.id,
            "disciplina_nome": ident.disciplina.nome,
            "id_aula": aula,
            "origem_disciplina": ident.origem,
        }

    final, meta = resumo.resumir(cfg, segmentos, progresso=progresso)
    meta["origem_legenda"] = origem_legenda
    markdown = notes.montar(
        cfg,
        disc_id=ident.disciplina.id,
        disc_nome=ident.disciplina.nome,
        aula_id=aula,
        video_id=video_id,
        video_titulo=video_titulo,
        canal=canal,
        pagina_url=pagina_url,
        pagina_titulo=pagina_titulo or video_titulo,
        idioma=idioma,
        auto_legenda=auto_legenda,
        resumo=final,
        meta=meta,
        segmentos=segmentos,
    )
    notes.salvar(caminho, markdown)
    notes.atualizar_indice(pasta)

    banco = Banco(cfg)
    try:
        banco.indexar(
            video_id=video_id,
            disciplina=ident.disciplina.id,
            data=data_iso,
            titulo=video_titulo,
            conteudo=markdown,
            caminho=caminho,
        )
    finally:
        banco.fechar()

    return {
        "estado": "pronto",
        "caminho": str(caminho),
        "disciplina": ident.disciplina.id,
        "disciplina_nome": ident.disciplina.nome,
        "id_aula": aula,
        "origem_disciplina": ident.origem,
        "meta": meta,
        "topicos": len(final.get("topicos", [])),
        "tarefas": len(final.get("tarefas", [])),
    }

