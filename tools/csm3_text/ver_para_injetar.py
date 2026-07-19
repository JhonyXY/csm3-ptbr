#!/usr/bin/env python3
"""O arquivo de injecao tem blocos com mais de uma linha?

O preparo diz que inseriu linhas, o injetor diz que inseriu zero. Um dos dois
esta enganado; este script olha o arquivo no meio do caminho.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).parent / "_out"


def main() -> int:
    dados = json.loads((OUT / "para_injetar.json").read_text(encoding="utf-8"))
    strings = dados["strings"]

    tipos = Counter(type(s.get("pt")).__name__ for s in strings)
    tamanhos = Counter(len(s["pt"]) if isinstance(s["pt"], list) else 1
                       for s in strings)

    print("=" * 74)
    print("PARA_INJETAR.JSON")
    print("=" * 74)
    print(f"  entradas        : {len(strings):,}")
    print(f"  tipo do campo pt: {dict(tipos)}")
    print(f"  linhas por bloco: {dict(sorted(tamanhos.items()))}")

    # offsets repetidos: o injetor guarda num dict, entao o ultimo vence
    offsets = Counter((s["script"], s["offset"]) for s in strings)
    repetidos = {k: v for k, v in offsets.items() if v > 1}
    print(f"  offsets repetidos: {len(repetidos)}")
    if repetidos:
        print("    ATENCAO: o injetor guarda por offset num dicionario, entao")
        print("    entradas repetidas se sobrescrevem. Exemplos:")
        for (script, off), n in list(repetidos.items())[:5]:
            print(f"      script {script} offset 0x{off:05X}: {n} entradas")

    print()
    print("  exemplos com mais de uma linha:")
    n = 0
    for s in strings:
        if isinstance(s["pt"], list) and len(s["pt"]) > 1:
            print(f"    script {s['script']} offset 0x{s['offset']:05X}")
            for l in s["pt"]:
                print(f"      | {l}")
            n += 1
            if n >= 4:
                break
    if n == 0:
        print("    NENHUM - o preparo nao esta gerando listas com varias linhas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
