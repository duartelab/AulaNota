from __future__ import annotations

import html
import re
from dataclasses import dataclass

RE_TEMPO = re.compile(r"(?:(\d{1,3}):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")
RE_TAG = re.compile(r"<[^>]+>")
RE_ENTIDADE = re.compile(r"&[a-zA-Z#0-9]+;")


@dataclass
class Segmento:
    inicio: float
    fim: float
    texto: str

    @property
    def marca(self) -> str:
        return hhmmss(self.inicio)


def hhmmss(segundos: float) -> str:
    segundos = max(0, int(segundos))
    h, resto = divmod(segundos, 3600)
    m, s = divmod(resto, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _tempo(t: str) -> float:
    m = RE_TEMPO.search(t.strip())
    if not m:
        return 0.0
    h = int(m.group(1) or 0)
    mi = int(m.group(2))
    se = int(m.group(3))
    frac = m.group(4)
    return h * 3600 + mi * 60 + se + int(frac.ljust(3, "0")[:3]) / 1000


def _limpar(texto: str) -> str:
    texto = RE_TAG.sub("", texto)
    texto = html.unescape(texto)
    texto = texto.replace("\u200b", "")
    return re.sub(r"\s+", " ", texto).strip()


def _blocos(texto: str) -> list[list[str]]:
    texto = texto.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    saida = []
    for bruto in re.split(r"\n\s*\n", texto):
        linhas = [l for l in bruto.split("\n") if l.strip()]
        if linhas:
            saida.append(linhas)
    return saida


def parse_vtt(texto: str) -> list[Segmento]:
    segmentos: list[Segmento] = []
    for linhas in _blocos(texto):
        idx = next((i for i, l in enumerate(linhas) if "-->" in l), None)
        if idx is None:
            continue
        m = re.match(r"\s*(.+?)\s*-->\s*(.+?)\s*$", linhas[idx])
        if not m:
            continue
        inicio = _tempo(m.group(1))
        fim = _tempo(m.group(2))
        corpo = _limpar(" ".join(linhas[idx + 1:]))
        if corpo:
            segmentos.append(Segmento(inicio, fim, corpo))
    return _deduplicar(segmentos)


def parse_xml_youtube(texto: str) -> list[Segmento]:
    segmentos = []
    for m in re.finditer(
        r'<text[^>]*start="([\d.]+)"[^>]*(?:dur="([\d.]+)")?[^>]*>(.*?)</text>',
        texto,
        re.S,
    ):
        inicio = float(m.group(1))
        dur = float(m.group(2) or 0)
        corpo = _limpar(m.group(3))
        if corpo:
            segmentos.append(Segmento(inicio, inicio + dur, corpo))
    return _deduplicar(segmentos)


def _norm(palavra: str) -> str:
    return re.sub(r"[^\wáàâãéêíóôõúüç]", "", palavra.lower())


def _deduplicar(segmentos: list[Segmento]) -> list[Segmento]:
    """Legendas automáticas do YouTube repetem o texto anterior a cada linha.

    Mantemos apenas as palavras novas de cada trecho, com o timestamp do trecho,
    para não duplicar conteúdo nem perder a marcação de tempo.
    """
    saida: list[Segmento] = []
    acumulado: list[str] = []
    for seg in segmentos:
        palavras = seg.texto.split()
        if not palavras:
            continue
        limite = min(len(acumulado), len(palavras), 80)
        sobreposicao = 0
        for k in range(limite, 0, -1):
            if [_norm(w) for w in acumulado[-k:]] == [_norm(w) for w in palavras[:k]]:
                sobreposicao = k
                break
        novas = palavras[sobreposicao:]
        if not novas:
            if saida:
                saida[-1].fim = max(saida[-1].fim, seg.fim)
            continue
        saida.append(Segmento(seg.inicio, seg.fim, " ".join(novas)))
        acumulado = acumulado + novas
    return saida


def parse(texto: str) -> list[Segmento]:
    if "<transcript" in texto or "<text " in texto:
        segs = parse_xml_youtube(texto)
        if segs:
            return segs
    if "WEBVTT" in texto or "-->" in texto:
        segs = parse_vtt(texto)
        if segs:
            return segs
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    if linhas:
        return [Segmento(i * 5.0, (i + 1) * 5.0, l) for i, l in enumerate(linhas)]
    return []


def para_texto_marcado(segmentos: list[Segmento], intervalo: float = 20.0) -> str:
    if not segmentos:
        return ""
    blocos: list[str] = []
    acumulado: list[str] = []
    inicio = segmentos[0].inicio
    ultimo = segmentos[0].inicio
    for seg in segmentos:
        if seg.inicio - inicio >= intervalo and acumulado:
            blocos.append(f"[{hhmmss(inicio)}] " + " ".join(acumulado))
            acumulado = []
            inicio = seg.inicio
        acumulado.append(seg.texto)
        ultimo = seg.fim
    if acumulado:
        blocos.append(f"[{hhmmss(inicio)}] " + " ".join(acumulado))
    return "\n\n".join(blocos)


def texto_corrido(segmentos: list[Segmento]) -> str:
    return " ".join(s.texto for s in segmentos)


def duracao(segmentos: list[Segmento]) -> float:
    return segmentos[-1].fim if segmentos else 0.0


def chunks(texto: str, max_palavras: int, sobreposicao: int) -> list[str]:
    paragrafos = [p.strip() for p in texto.split("\n\n") if p.strip()]
    saida: list[str] = []
    atual: list[str] = []
    contagem = 0
    for p in paragrafos:
        n = len(p.split())
        if atual and contagem + n > max_palavras:
            saida.append("\n\n".join(atual))
            cauda = atual[-2:] if sobreposicao and len(atual) > 2 else []
            atual = list(cauda)
            contagem = sum(len(x.split()) for x in atual)
        atual.append(p)
        contagem += n
    if atual:
        saida.append("\n\n".join(atual))
    return saida or ([texto] if texto.strip() else [])
