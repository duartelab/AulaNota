from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from .config import Config


class OllamaError(RuntimeError):
    pass


def _post(cfg: Config, payload: dict, timeout: float) -> dict:
    url = cfg.ollama_url.rstrip("/") + "/api/chat"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", "replace")[:400]
        raise OllamaError(f"Ollama respondeu {e.code}: {corpo}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise OllamaError(
            f"Ollama indisponível em {cfg.ollama_url}. Rode: systemctl --user start ollama"
        ) from e


def _extrair_json(texto: str) -> dict:
    t = (texto or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\n?", "", t)
        t = re.sub(r"\n?```\s*$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        i, j = t.find("{"), t.rfind("}")
        if i >= 0 and j > i:
            return json.loads(t[i : j + 1])
        raise


def chat_json(cfg: Config, sistema: str, usuario: str, timeout: float = 300) -> dict:
    payload = {
        "model": cfg.modelo,
        "stream": False,
        "format": "json",
        "think": False,
        "messages": [
            {"role": "system", "content": sistema},
            {"role": "user", "content": usuario},
        ],
        "options": {
            "temperature": cfg.temperatura,
            "num_ctx": cfg.num_ctx,
            "num_predict": 1600,
            "repeat_penalty": 1.1,
        },
    }
    resposta = _post(cfg, payload, timeout)
    conteudo = (resposta.get("message") or {}).get("content", "")
    return _extrair_json(conteudo)


def vivo(cfg: Config) -> tuple[bool, list[str]]:
    try:
        with urllib.request.urlopen(cfg.ollama_url.rstrip("/") + "/api/tags", timeout=4) as r:
            dados = json.loads(r.read().decode())
        return True, [m.get("name", "") for m in dados.get("models", [])]
    except Exception:
        return False, []
