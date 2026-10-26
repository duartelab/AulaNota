from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from . import vtt
from .config import Config
from .identify import limpar_titulo


def _q(valor: str) -> str:
    return json.dumps(str(valor or ""), ensure_ascii=False)


def _lista_yaml(valores: list[str]) -> str:
    return "[" + ", ".join(_q(v) for v in valores) + "]"


def _frontmatter(dados: dict[str, object]) -> str:
    linhas = ["---"]
    for chave, valor in dados.items():
        if isinstance(valor, list):
            linhas.append(f"{chave}: {_lista_yaml([str(v) for v in valor])}")
        elif isinstance(valor, bool):
            linhas.append(f"{chave}: {'true' if valor else 'false'}")
        elif isinstance(valor, int):
            linhas.append(f"{chave}: {valor}")
        else:
            linhas.append(f"{chave}: {_q(str(valor))}")
    linhas.append("---")
    return "\n".join(linhas)


def _secao_resumo(itens: list[str]) -> str:
    if not itens:
        return ""
    return "## Resumo\n\n" + "\n".join(f"- {x}" for x in itens) + "\n"


def _secao_conceitos(itens: list[dict]) -> str:
    if not itens:
        return ""
    linhas = ["## Conceitos-chave", "", "| Termo | Definição |", "| --- | --- |"]
    for c in itens:
        termo = c['termo'].replace("|", "\\|")
        definicao = c['definicao'].replace("|", "\\|")
        linhas.append(f"| **{termo}** | {definicao} |")
    return "\n".join(linhas) + "\n"


def _secao_topicos(itens: list[dict]) -> str:
    if not itens:
        return ""
    partes = ["## Desenvolvimento"]
    for t in itens:
        marcas = " · ".join(f"`{x}`" for x in t["timestamps"])
        titulo = f"### {t['titulo']}"
        if marcas:
            titulo += f"  \n{marcas}"
        partes.append(titulo)
        partes.extend(f"- {p}" for p in t["pontos"])
        partes.append("")
    return "\n".join(partes)


def _secao_formulas(itens: list[dict]) -> str:
    if not itens:
        return ""
    linhas = ["## Fórmulas", ""]
    for f in itens:
        marca = f" `{f['timestamp']}`" if f["timestamp"] else ""
        linhas.append(f"- `{f['expressao']}`{marca} — {f['explicacao']}")
    return "\n".join(linhas) + "\n"


def _secao_exemplos(itens: list[dict]) -> str:
    if not itens:
        return ""
    linhas = ["## Exemplos", ""]
    for e in itens:
        marca = f" `{e['timestamp']}`" if e["timestamp"] else ""
        linhas.append(f"- {e['descricao']}{marca}")
    return "\n".join(linhas) + "\n"


def _secao_duvidas(itens: list[str]) -> str:
    if not itens:
        return ""
    return "## Pontos de dúvida\n\n" + "\n".join(f"- {x}" for x in itens) + "\n"


def _secao_tarefas(itens: list[dict]) -> str:
    if not itens:
        return ""
    linhas = ["## Tarefas e prazos", ""]
    for t in itens:
        linhas.append(f"- **{t['descricao']}**")
        detalhes = []
        if t["prazo_dito"]:
            detalhes.append(f'prazo dito: "{t["prazo_dito"]}"')
        if t["timestamp"]:
            detalhes.append(f"ouvido em `{t['timestamp']}`")
        if detalhes:
            linhas.append("  - " + " · ".join(detalhes))
        if t["evidencia"]:
            linhas.append(f"  - evidência: {t['evidencia']}")
    return "\n".join(linhas) + "\n"


def _secao_perguntas(itens: list[str]) -> str:
    if not itens:
        return ""
    linhas = ["## Perguntas de revisão", ""]
    for i, pergunta in enumerate(itens[:12], 1):
        linhas.append(f"{i}. {pergunta}")
    return "\n".join(linhas) + "\n"


def _secao_transcricao(segmentos: list[vtt.Segmento]) -> str:
    if not segmentos:
        return ""
    linhas = ["", "<details>", "<summary>Transcrição completa</summary>", ""]
    for s in segmentos:
        linhas.append(f"`{s.marca}` {s.texto}")
    linhas.extend(["", "</details>", ""])
    return "\n".join(linhas)


def montar(
    cfg: Config,
    *,
    disc_id: str,
    disc_nome: str,
    aula_id: str,
    video_id: str,
    video_titulo: str,
    canal: str,
    pagina_url: str,
    pagina_titulo: str,
    idioma: str,
    auto_legenda: bool,
    resumo: dict,
    meta: dict,
    segmentos: list[vtt.Segmento],
) -> str:
    agora = datetime.now()
    dados_fm = {
        "id_disciplina": disc_id,
        "disciplina": disc_nome,
        "id_aula": aula_id,
        "video_id": video_id,
        "data": agora.date().isoformat(),
        "hora": agora.strftime("%H:%M"),
        "titulo": limpar_titulo(video_titulo) or video_titulo,
        "canal": canal,
        "idioma_legenda": idioma,
        "legenda_automatica": auto_legenda,
        "pagina": pagina_url,
        "pagina_titulo": pagina_titulo,
        "duracao": vtt.hhmmss(meta.get("duracao_seg", 0)),
        "partes": meta.get("partes", 1),
        "falhas": meta.get("falhas", []),
        "modelo": cfg.modelo,
        "origem_legenda": meta.get("origem_legenda", "recebida"),
        "gerado_em": agora.isoformat(timespec="seconds"),
        "tags": ["aula", disc_id],
    }
    corpo = [
        _frontmatter(dados_fm),
        "",
        f"# {dados_fm['titulo']}",
        "",
        f"**Disciplina:** {disc_nome} (`{disc_id}`) · **Data:** {dados_fm['data']} · "
        f"**Duração:** {dados_fm['duracao']} · **Fonte:** {pagina_url or 'YouTube'}",
        "",
    ]
    if meta.get("falhas"):
        corpo.append(
            "> **Atenção:** algumas partes da transcrição não puderam ser resumidas "
            f"(partes {', '.join(map(str, meta['falhas']))}). A nota pode estar incompleta.\n"
        )

    for secao in (
        _secao_resumo(resumo.get("resumo", [])),
        _secao_conceitos(resumo.get("conceitos", [])),
        _secao_topicos(resumo.get("topicos", [])),
        _secao_formulas(resumo.get("formulas", [])),
        _secao_exemplos(resumo.get("exemplos", [])),
        _secao_duvidas(resumo.get("duvidas", [])),
        _secao_tarefas(resumo.get("tarefas", [])),
        _secao_perguntas(resumo.get("perguntas", [])),
    ):
        if secao:
            corpo.append(secao)

    if cfg.incluir_transcricao:
        corpo.append(_secao_transcricao(segmentos))

    return "\n".join(corpo).rstrip() + "\n"


def nome_arquivo(data_iso: str, aula_id: str) -> str:
    seguro = re.sub(r"[^A-Za-z0-9._-]+", "-", aula_id).strip("-")
    return f"{data_iso}_{seguro}.md"


def salvar(caminho: Path, conteudo: str) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    tmp.write_text(conteudo, encoding="utf-8")
    tmp.replace(caminho)
    return caminho


def atualizar_indice(pasta: Path) -> Path:
    linhas = [
        f"# {pasta.name} — índice de aulas",
        "",
        "Atualizado automaticamente pelo AulaNota.",
        "",
        "| Data | Aula | Arquivo | Duração |",
        "| --- | --- | --- | --- |",
    ]
    arquivos = sorted(pasta.glob("*.md"), reverse=True)
    for arq in arquivos:
        if arq.name.startswith("_"):
            continue
        texto = arq.read_text(encoding="utf-8", errors="replace")[:1200]
        data = _campo(texto, "data") or ""
        titulo = _campo(texto, "titulo") or arq.stem
        dur = _campo(texto, "duracao") or ""
        linhas.append(f"| {data} | {titulo} | [[{arq.stem}]] | {dur} |")
    destino = pasta / "_indice.md"
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return destino


def _campo(texto: str, chave: str) -> str:
    m = re.search(rf'^{chave}:\s*"?(.*?)"?\s*$', texto, re.M)
    return m.group(1).strip() if m else ""
