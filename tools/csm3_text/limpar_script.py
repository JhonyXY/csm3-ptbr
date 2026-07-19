#!/usr/bin/env python3
"""Apaga as traducoes de um script, para refazer com o orcamento certo.

O orcamento por fala mudou: era o mesmo para todas, e agora conta as linhas
disponiveis (25 caracteres por linha de tela). O que foi traduzido com o
orcamento antigo pode nao caber, entao vale refazer.

    python3 limpar_script.py 1603
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = Path(__file__).parent / "_out"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    alvos = {int(s) for s in sys.argv[1].split(",")}

    originais = json.loads(
        (OUT / "falas_originais.json").read_text(encoding="utf-8"))
    ids = {e["id"] for e in originais["falas"] + originais.get("itens", [])
           if e.get("script") in alvos}

    caminho = OUT / "traducao.json"
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    antes = len(dados["traducoes"])
    dados["traducoes"] = [t for t in dados["traducoes"]
                          if t.get("id") not in ids]
    caminho.write_text(json.dumps(dados, indent=2, ensure_ascii=False),
                       encoding="utf-8")

    print(f"  scripts {sorted(alvos)}")
    print(f"  removidas : {antes - len(dados['traducoes'])}")
    print(f"  restam    : {len(dados['traducoes']):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
