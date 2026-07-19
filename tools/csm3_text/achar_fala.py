#!/usr/bin/env python3
"""Onde, na ROM, esta uma fala que eu vi na tela?

Numero de script NAO e ordem da historia - descobri isso injetando os 120
scripts de menor numero e a introducao nao estar entre eles. Com um trecho do
japones que aparece na tela, este script diz em que script a cena mora, e
quais scripts sao seus vizinhos na mesma cena.

    python3 achar_fala.py 'ありがとう'
    python3 achar_fala.py --contexto 12   # mostra as falas vizinhas
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

OUT = Path(__file__).parent / "_out"


def main() -> int:
    args = [a for a in sys.argv[1:]]
    contexto = 0
    if "--contexto" in args:
        i = args.index("--contexto")
        contexto = int(args[i + 1])
        del args[i:i + 2]
    if not args:
        print(__doc__)
        return 1
    alvo = args[0]

    dados = json.loads((OUT / "falas_originais.json").read_text(encoding="utf-8"))
    falas = dados["falas"] + dados.get("itens", [])

    achados = [e for e in falas if alvo in e.get("jp", "")]

    print("=" * 74)
    print(f"BUSCA: {alvo!r}")
    print("=" * 74)
    print(f"  ocorrencias: {len(achados)}")

    if not achados:
        print("\n  nao achei. Tente um trecho menor.")
        return 1

    scripts = Counter(e["script"] for e in achados)
    print(f"  scripts     : {sorted(scripts)}")
    print()

    for e in achados[:6]:
        print(f"  script {e['script']:4d}  offset 0x{e['offset']:05X}  id {e['id']}")
        print(f"    {e['jp'][:70]}")
        ctx = e.get("contexto") or {}
        if ctx.get("antes"):
            print(f"    antes : {str(ctx['antes'])[:60]}")
        if ctx.get("depois"):
            print(f"    depois: {str(ctx['depois'])[:60]}")
        print()

    if contexto:
        script = achados[0]["script"]
        vizinhas = sorted((e for e in falas if e["script"] == script),
                          key=lambda x: x["offset"])
        print("=" * 74)
        print(f"CENA COMPLETA - script {script} ({len(vizinhas)} falas)")
        print("=" * 74)
        for e in vizinhas[:contexto]:
            marca = " <<<" if alvo in e.get("jp", "") else ""
            print(f"  0x{e['offset']:05X}  {e['jp'][:62]}{marca}")

    # Quantos scripts a cena provavelmente ocupa: os offsets proximos.
    print()
    print("=" * 74)
    print("PARA INJETAR ESTA PARTE")
    print("=" * 74)
    lista = sorted(scripts)
    print(f"  scripts envolvidos: {lista}")
    print(f"\n  python3 preparar_injecao.py --scripts={','.join(map(str, lista))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
