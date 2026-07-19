#!/usr/bin/env python3
"""Como o id de uma fala se decompoe em script e offset?

O injetor casou so 24 de 4.189 ocorrencias, o que significa que estou lendo o
id errado. Este script compara o id com os campos que export_falas.py ja grava
em falas_originais.json, em vez de eu adivinhar a base numerica.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).parent / "_out"


def main() -> int:
    dados = json.loads((OUT / "falas_originais.json").read_text(encoding="utf-8"))
    falas = dados["falas"]

    print("=" * 74)
    print("ESTRUTURA DE UMA FALA")
    print("=" * 74)
    print(f"  total: {len(falas):,}")
    print(f"  campos: {sorted(falas[0].keys())}")
    print()
    print("  primeiras 6 entradas:")
    for e in falas[:6]:
        campos = {k: v for k, v in e.items() if k != "jp"}
        print(f"    {campos}")
        print(f"      jp: {e['jp'][:50]}")

    print()
    print("=" * 74)
    print("O ID BATE COM QUAL LEITURA?")
    print("=" * 74)
    hex_ok = dec_ok = misto_ok = 0
    for e in falas[:400]:
        ident = str(e.get("id", ""))
        if "_" not in ident:
            continue
        esq, dir_ = ident.lstrip("f").split("_", 1)
        s = e.get("script")
        o = e.get("offset")
        if s is None or o is None:
            continue
        try:
            if int(esq, 16) == s and int(dir_, 16) == o:
                hex_ok += 1
            if int(esq, 10) == s and int(dir_, 10) == o:
                dec_ok += 1
            if int(esq, 10) == s and int(dir_, 16) == o:
                misto_ok += 1
        except ValueError:
            pass

    print(f"  script hex + offset hex : {hex_ok}")
    print(f"  script dec + offset dec : {dec_ok}")
    print(f"  script dec + offset hex : {misto_ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
