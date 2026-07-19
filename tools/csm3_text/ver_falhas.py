#!/usr/bin/env python3
"""Mostra o que falhou na traducao, agrupado por motivo.

Existe para eu nao deixar 16 horas de rodagem passar com um modo de falha
sistematico que so apareceria no fim.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

OUT = Path(__file__).parent / "_out"


def main() -> int:
    nome = sys.argv[1] if len(sys.argv) > 1 else "traducao.json"
    caminho = OUT / nome
    if not caminho.exists():
        print(f"  ainda nao existe: {caminho}")
        return 1

    dados = json.loads(caminho.read_text(encoding="utf-8"))
    trad = dados.get("traducoes", [])
    falhas = [e for e in trad if e.get("erro") or not e.get("pt")]

    print("=" * 72)
    print("FALHAS DA TRADUCAO")
    print("=" * 72)
    print(f"  gravadas : {len(trad):,}")
    print(f"  falhas   : {len(falhas):,}")
    if trad:
        print(f"  taxa     : {100 * len(falhas) / len(trad):.1f}%")

    if not falhas:
        print("\n  Nenhuma falha.")
        return 0

    print("\n  motivos:")
    for motivo, n in Counter(str(e.get("erro"))[:70] for e in falhas).most_common():
        print(f"    {n:5d}x  {motivo}")

    print("\n  amostras:")
    for e in falhas[:6]:
        print()
        print(f"    id  : {e.get('id')}")
        print(f"    jp  : {str(e.get('jp'))[:100]}")
        print(f"    pt  : {str(e.get('pt'))[:100]}")
        print(f"    erro: {str(e.get('erro'))[:200]}")

    # O que separa quem falhou de quem passou? Se for so tamanho, e contexto.
    ok = [e for e in trad if e.get("pt") and not e.get("erro")]
    if ok and falhas:
        def med(xs):
            return sum(len(str(e.get("jp", ""))) for e in xs) / len(xs)
        print()
        print(f"  tamanho medio do japones: falhas {med(falhas):.0f} chars, "
              f"sucessos {med(ok):.0f} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
