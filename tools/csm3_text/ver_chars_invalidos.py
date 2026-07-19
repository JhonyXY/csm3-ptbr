#!/usr/bin/env python3
"""Quais caracteres das traducoes a fonte do jogo nao sabe representar?

Levantar todos de uma vez e melhor que descobrir um por um a cada injecao que
falha. Mostra tambem quantas falas cada um afeta, para decidir se vale um
substituto ou se e caso de reescrever a fala.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import encoder

OUT = Path(__file__).parent / "_out"


def main() -> int:
    nome = sys.argv[1] if len(sys.argv) > 1 else "traducao.json"
    dados = json.loads((OUT / nome).read_text(encoding="utf-8"))

    ruins = Counter()
    exemplos = {}
    total = 0

    for e in dados.get("traducoes", []):
        pt = (e.get("pt") or "").strip()
        if not pt or e.get("erro"):
            continue
        total += 1
        for ch in set(pt):
            try:
                encoder.encode(ch)
            except Exception:
                ruins[ch] += 1
                exemplos.setdefault(ch, pt)

    print("=" * 74)
    print("CARACTERES QUE A FONTE NAO REPRESENTA")
    print("=" * 74)
    print(f"  falas conferidas: {total:,}")
    print(f"  caracteres problematicos: {len(ruins)}")
    print()

    if not ruins:
        print("  Nenhum. Pode injetar.")
        return 0

    print(f"  {'char':6s} {'U+':8s} {'falas':>6s}  exemplo")
    print("  " + "-" * 68)
    for ch, n in ruins.most_common():
        ex = exemplos[ch]
        i = ex.find(ch)
        trecho = ex[max(0, i - 22): i + 22].replace("\n", " ")
        print(f"  {ch!r:6s} U+{ord(ch):04X}  {n:6d}  ...{trecho}...")

    print()
    print("  Some destes tem substituto obvio ('4o' no lugar de '4 ordinal').")
    print("  Outros indicam que o modelo saiu do portugues esperado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
