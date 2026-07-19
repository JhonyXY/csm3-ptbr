#!/usr/bin/env python3
"""O preparo diz que inseriu linhas; o arquivo sai com uma linha por bloco.
Um dos dois mente. Este script roda a quebra a mao numa fala conhecida.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

import preparar_injecao as prep

OUT = Path(__file__).parent / "_out"


def main() -> int:
    largura = prep.carregar_larguras()
    originais = json.loads(
        (OUT / "falas_originais.json").read_text(encoding="utf-8"))
    trad = json.loads((OUT / "traducao.json").read_text(encoding="utf-8"))
    por_id = {t["id"]: t for t in trad["traducoes"] if t.get("pt")}

    falas = [e for e in originais["falas"] if e.get("script") == 1603]
    print("=" * 74)
    print("QUEBRA, FALA A FALA (script 1603)")
    print("=" * 74)

    contador = Counter()
    mostrados = 0
    for e in falas:
        t = por_id.get(e["id"])
        if not t:
            continue
        pt = prep.normalizar(t["pt"].strip(), Counter())
        blocos = [b["offset"] for b in e.get("estrutura") or []]
        linhas = prep.quebrar(pt, largura)
        reparte = prep.distribuir(linhas, len(blocos), contador)
        if len(linhas) > len(blocos) and mostrados < 6:
            mostrados += 1
            print()
            print(f"  {e['id']}  blocos={len(blocos)}  linhas={len(linhas)}")
            print(f"    pt: {pt}")
            for i, grupo in enumerate(reparte):
                print(f"    bloco {i}: {grupo}")

    print()
    print(f"  contador: {dict(contador)}")
    print(f"  falas que precisam de linha extra: {sum(contador.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
