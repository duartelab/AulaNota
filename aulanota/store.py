from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .config import Config


class Banco:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        cfg.pasta_estado.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(cfg.banco)
        self.con.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS notas USING fts5(
                video_id UNINDEXED,
                disciplina UNINDEXED,
                data UNINDEXED,
                titulo,
                conteudo,
                caminho UNINDEXED
            )
            """
        )
        self.con.commit()

    def indexar(
        self,
        *,
        video_id: str,
        disciplina: str,
        data: str,
        titulo: str,
        conteudo: str,
        caminho: Path,
    ) -> None:
        self.con.execute("DELETE FROM notas WHERE video_id = ?", (video_id,))
        self.con.execute(
            "INSERT INTO notas (video_id, disciplina, data, titulo, conteudo, caminho) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (video_id, disciplina, data, titulo, conteudo, str(caminho)),
        )
        self.con.commit()

    def recentes(self, limite: int = 20) -> list[dict]:
        cur = self.con.execute(
            "SELECT video_id, disciplina, data, titulo, caminho FROM notas "
            "ORDER BY data DESC LIMIT ?",
            (limite,),
        )
        return [self._linha(r) for r in cur.fetchall()]

    def buscar(self, termo: str, limite: int = 30) -> list[dict]:
        consulta = termo.replace('"', '""')
        cur = self.con.execute(
            "SELECT video_id, disciplina, data, titulo, caminho, "
            "snippet(notas, 4, '<<', '>>', ' … ', 18) FROM notas "
            "WHERE notas MATCH ? ORDER BY rank LIMIT ?",
            (f'"{consulta}"', limite),
        )
        saida = []
        for r in cur.fetchall():
            item = self._linha(r[:5])
            item["trecho"] = r[5]
            saida.append(item)
        return saida

    def total(self) -> int:
        return self.con.execute("SELECT count(*) FROM notas").fetchone()[0]

    @staticmethod
    def _linha(r) -> dict:
        return {
            "video_id": r[0],
            "disciplina": r[1],
            "data": r[2],
            "titulo": r[3],
            "caminho": r[4],
        }

    def fechar(self) -> None:
        self.con.close()
