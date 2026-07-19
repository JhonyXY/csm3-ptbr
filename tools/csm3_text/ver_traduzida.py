#!/usr/bin/env python3
"""Esta fala ja foi traduzida? E se foi, entrou na ROM?

Sao tres perguntas diferentes que costumam ser confundidas:
  1. o tradutor ja produziu portugues para ela?
  2. ela entrou no recorte que foi injetado?
  3. o script dela cabe no espaco livre?

    python3 ver_traduzida.py 'ありがとう'
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
    alvo = sys.argv[1]

    originais = json.loads(
        (OUT / "falas_originais.json").read_text(encoding="utf-8"))
    falas = originais["falas"] + originais.get("itens", [])
    achados = [e for e in falas if alvo in e.get("jp", "")]

    if not achados:
        print(f"  nao achei {alvo!r} no texto extraido")
        return 1

    trad = json.loads((OUT / "traducao.json").read_text(encoding="utf-8"))
    por_jp = {}
    for e in trad.get("traducoes", []):
        if e.get("pt") and not e.get("erro"):
            por_jp[e["jp"]] = e["pt"]

    injetado = set()
    caminho = OUT / "para_injetar.json"
    if caminho.exists():
        for s in json.loads(caminho.read_text(encoding="utf-8"))["strings"]:
            injetado.add((s["script"], s["offset"]))

    print("=" * 74)
    print(f"BUSCA: {alvo!r}   ({len(achados)} ocorrencias)")
    print("=" * 74)

    for e in achados[:8]:
        pt = por_jp.get(e["jp"])
        na_rom = (e["script"], e["offset"]) in injetado
        print()
        print(f"  script {e['script']:4d}  offset 0x{e['offset']:05X}")
        print(f"    jp : {e['jp'][:64]}")
        if pt:
            print(f"    pt : {pt[:64]}")
            print(f"    -> traduzida SIM   |   na ROM injetada: "
                  f"{'SIM' if na_rom else 'NAO (fora do recorte)'}")
        else:
            print(f"    -> traduzida NAO (o tradutor ainda nao chegou nela)")

    # Panorama do script inteiro
    script = achados[0]["script"]
    do_script = [e for e in falas if e["script"] == script]
    feitas = sum(1 for e in do_script if por_jp.get(e["jp"]))
    na_rom = sum(1 for e in do_script
                 if (e["script"], e["offset"]) in injetado)
    print()
    print("=" * 74)
    print(f"O SCRIPT {script} INTEIRO")
    print("=" * 74)
    print(f"  falas          : {len(do_script)}")
    print(f"  traduzidas     : {feitas}  ({100*feitas/len(do_script):.0f}%)")
    print(f"  injetadas      : {na_rom}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
