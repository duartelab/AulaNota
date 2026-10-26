from __future__ import annotations

import json
import os
import re

from . import ollama, vtt
from .config import Config

SISTEMA = """Você é um assistente que transforma a transcrição literal de uma aula em notas de estudo.
Regras obrigatórias:
1. Use SOMENTE o conteúdo da transcrição fornecida. Não invente fatos, definições, números, fórmulas, nomes, datas ou prazos.
2. Se uma informação não estiver na transcrição, deixe a lista vazia ou o campo como string vazia. Nunca preencha por dedução.
3. Preserve termos técnicos, siglas e fórmulas exatamente como aparecem.
4. Escreva em português do Brasil, de forma clara e objetiva.
5. Timestamps devem ser copiados EXATAMENTE de um marcador [hh:mm:ss] presente no texto. Use o marcador imediatamente anterior ao trecho. Nunca invente um horário.
6. Em "tarefas", inclua algo apenas se houver: (a) prazo/data, (b) as palavras entrega, prova, avaliação, trabalho ou exercício, ou (c) instrução direta no imperativo (leia, faça, resolva, entregue, estude). Ignore inscrição no canal, Patreon, likes, exemplos hipotéticos, desafios motivacionais e descrições de funcionamento.
7. Seja econômico: no máximo 8 itens em "resumo", 12 em "conceitos", 10 em "topicos", 8 em "tarefas" e 8 em "perguntas". Não repita o mesmo conceito com nomes diferentes.
8. Responda APENAS com JSON válido, sem comentários e sem markdown.
"""

ESQUEMA = """{
  "resumo": ["5 a 8 frases curtas com as ideias centrais da aula"],
  "conceitos": [{"termo": "termo", "definicao": "definição dada na aula"}],
  "topicos": [{"titulo": "nome do tópico", "pontos": ["ponto explicado"], "timestamps": ["hh:mm:ss"]}],
  "formulas": [{"expressao": "fórmula como foi dita", "explicacao": "o que ela representa", "timestamp": "hh:mm:ss"}],
  "exemplos": [{"descricao": "exemplo dado pelo professor", "timestamp": "hh:mm:ss"}],
  "duvidas": ["perguntas levantadas ou pontos que ficaram em aberto"],
  "tarefas": [{"descricao": "tarefa, exercício, leitura ou prova mencionada", "prazo_dito": "prazo nas palavras do professor, ou vazio", "timestamp": "hh:mm:ss", "evidencia": "trecho da transcrição que comprova"}],
  "perguntas": ["pergunta de revisão que possa ser respondida com o conteúdo da aula"]
}"""


def _s(valor) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _lista(valor) -> list:
    return valor if isinstance(valor, list) else []


def _seg(t: str) -> int:
    partes = [int(x) for x in t.split(":")]
    if len(partes) == 2:
        return partes[0] * 60 + partes[1]
    return partes[0] * 3600 + partes[1] * 60 + partes[2]


def _fmt(s: int) -> str:
    h, resto = divmod(s, 3600)
    m, seg = divmod(resto, 60)
    return f"{h:02d}:{m:02d}:{seg:02d}" if h else f"{m:02d}:{seg:02d}"


def _ts(valor: str, marcadores: list[str]) -> str:
    """Aceita só horários que existem na transcrição; caso contrário, aproxima."""
    valor = (valor or "").strip()
    if not re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", valor):
        return ""
    if valor in marcadores:
        return valor
    if not marcadores:
        return ""
    alvo = _seg(valor)
    melhor = min(marcadores, key=lambda m: abs(_seg(m) - alvo))
    return melhor if abs(_seg(melhor) - alvo) <= 90 else ""


def _normalizar(dados: dict, marcadores: list[str] | None = None) -> dict:
    marcadores = marcadores or []
    saida = {
        "resumo": [x for x in (_s(v) for v in _lista(dados.get("resumo"))) if x],
        "conceitos": [],
        "topicos": [],
        "formulas": [],
        "exemplos": [],
        "duvidas": [x for x in (_s(v) for v in _lista(dados.get("duvidas"))) if x],
        "tarefas": [],
        "perguntas": [x for x in (_s(v) for v in _lista(dados.get("perguntas"))) if x],
    }
    for c in _lista(dados.get("conceitos")):
        if isinstance(c, dict) and _s(c.get("termo")):
            saida["conceitos"].append(
                {"termo": _s(c.get("termo")), "definicao": _s(c.get("definicao"))}
            )
    for t in _lista(dados.get("topicos")):
        if isinstance(t, dict) and _s(t.get("titulo")):
            marcas = [x for x in (_ts(v, marcadores) for v in _lista(t.get("timestamps"))) if x]
            saida["topicos"].append(
                {
                    "titulo": _s(t.get("titulo")),
                    "pontos": [x for x in (_s(v) for v in _lista(t.get("pontos"))) if x],
                    "timestamps": _unico(marcas, lambda x: x),
                }
            )
    for f in _lista(dados.get("formulas")):
        if isinstance(f, dict) and _s(f.get("expressao")):
            saida["formulas"].append(
                {
                    "expressao": _s(f.get("expressao")),
                    "explicacao": _s(f.get("explicacao")),
                    "timestamp": _ts(_s(f.get("timestamp")), marcadores),
                }
            )
    for e in _lista(dados.get("exemplos")):
        if isinstance(e, dict) and _s(e.get("descricao")):
            saida["exemplos"].append(
                {"descricao": _s(e.get("descricao")), "timestamp": _ts(_s(e.get("timestamp")), marcadores)}
            )
    for t in _lista(dados.get("tarefas")):
        if isinstance(t, dict) and _s(t.get("descricao")):
            saida["tarefas"].append(
                {
                    "descricao": _s(t.get("descricao")),
                    "prazo_dito": _s(t.get("prazo_dito")),
                    "timestamp": _ts(_s(t.get("timestamp")), marcadores),
                    "evidencia": _s(t.get("evidencia")),
                }
            )
    for chave, limite in (
        ("resumo", 8), ("conceitos", 12), ("topicos", 10), ("formulas", 10),
        ("exemplos", 8), ("duvidas", 8), ("tarefas", 8), ("perguntas", 8),
    ):
        saida[chave] = saida[chave][:limite]
    return saida


def _unico(itens: list, chave) -> list:
    vistos: set[str] = set()
    saida = []
    for item in itens:
        k = re.sub(r"\s+", " ", chave(item).strip().lower())
        if k and k not in vistos:
            vistos.add(k)
            saida.append(item)
    return saida


def _merge_deterministico(parciais: list[dict]) -> dict:
    resumo = _unico(
        [{"t": x} for p in parciais for x in p["resumo"]], lambda i: i["t"]
    )[:10]
    conceitos = _unico(
        [c for p in parciais for c in p["conceitos"]], lambda c: c["termo"]
    )
    formulas = _unico(
        [f for p in parciais for f in p["formulas"]], lambda f: f["expressao"]
    )
    exemplos = _unico(
        [e for p in parciais for e in p["exemplos"]], lambda e: e["descricao"]
    )
    tarefas = _unico(
        [t for p in parciais for t in p["tarefas"]], lambda t: t["descricao"]
    )
    duvidas = _unico([d for p in parciais for d in p["duvidas"]], lambda d: d)
    perguntas = _unico([x for p in parciais for x in p.get("perguntas", [])], lambda x: x)
    topicos_map: dict[str, dict] = {}
    ordem: list[str] = []
    for p in parciais:
        for t in p["topicos"]:
            k = re.sub(r"\s+", " ", t["titulo"].strip().lower())
            if k not in topicos_map:
                topicos_map[k] = {"titulo": t["titulo"], "pontos": [], "timestamps": []}
                ordem.append(k)
            atual = topicos_map[k]
            atual["pontos"] = _unico(atual["pontos"] + t["pontos"], lambda x: x)
            atual["timestamps"] = _unico(atual["timestamps"] + t["timestamps"], lambda x: x)
    return {
        "resumo": [x["t"] for x in resumo],
        "conceitos": conceitos,
        "topicos": [topicos_map[k] for k in ordem],
        "formulas": formulas,
        "exemplos": exemplos,
        "duvidas": duvidas,
        "tarefas": tarefas,
        "perguntas": perguntas,
    }


def _merge_llm(cfg: Config, parciais: list[dict]) -> dict | None:
    compacto = json.dumps(parciais, ensure_ascii=False, separators=(",", ":"))
    if len(compacto) > 22000:
        return None
    usuario = (
        "Abaixo estão resumos parciais da MESMA aula, em ordem. "
        "Una tudo em um único JSON no esquema pedido. "
        "Remova repetições, preserve timestamps e não acrescente nenhuma informação nova.\n\n"
        f"Esquema:\n{ESQUEMA}\n\nParciais:\n{compacto}"
    )
    try:
        marcadores = re.findall(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]", json.dumps(parciais))
        return _normalizar(ollama.chat_json(cfg, SISTEMA, usuario, timeout=300), marcadores)
    except Exception:
        return None


def resumir(cfg: Config, segmentos: list[vtt.Segmento], progresso=None) -> tuple[dict, dict]:
    texto = vtt.para_texto_marcado(segmentos)
    partes = vtt.chunks(texto, cfg.max_palavras_chunk, cfg.sobreposicao_palavras)
    parciais: list[dict] = []
    falhas: list[int] = []

    for i, parte in enumerate(partes, 1):
        if progresso:
            try:
                progresso(f"resumindo parte {i} de {len(partes)}", i, len(partes))
            except Exception:
                pass
        usuario = (
            f"Esta é a parte {i} de {len(partes)} da transcrição da aula.\n\n"
            f"Esquema de saída:\n{ESQUEMA}\n\n"
            f"Transcrição:\n{parte}"
        )
        try:
            dados = ollama.chat_json(cfg, SISTEMA, usuario)
            marcadores = re.findall(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]", parte)
            parciais.append(_normalizar(dados, marcadores))
        except Exception:
            falhas.append(i)

    if not parciais:
        raise ollama.OllamaError(
            "Não foi possível resumir nenhuma parte da aula com o Ollama."
        )

    if len(parciais) == 1:
        final = parciais[0]
    elif os.environ.get("AULANOTA_MERGE_LLM") == "1":
        final = _merge_llm(cfg, parciais) or _merge_deterministico(parciais)
    else:
        final = _merge_deterministico(parciais)

    meta = {
        "partes": len(partes),
        "partes_ok": len(parciais),
        "falhas": falhas,
        "palavras_transcricao": len(vtt.texto_corrido(segmentos).split()),
        "duracao_seg": vtt.duracao(segmentos),
    }
    return final, meta
