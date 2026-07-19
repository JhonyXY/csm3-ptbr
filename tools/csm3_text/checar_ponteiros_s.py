#!/usr/bin/env python3
"""Confere como cada um dos 43 ponteiros aparece em data/*.s."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"

INCBIN = re.compile(r'^\s*\.incbin\s+"baserom\.gba",\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+)')
LABEL = re.compile(r"^(\w+)::")


def main() -> int:
    dados = json.loads((OUT / "sysstrings.json").read_text(encoding="utf-8"))
    ponteiros = [e["ponteiro"] for e in dados["strings"]]

    # Indexa todos os blocos de data/
    blocos = []
    for path in sorted((REPO / "data").glob("*.s")):
        if path.name == "ptbr.s":
            continue
        label = None
        for i, linha in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            m = LABEL.match(linha)
            if m:
                label = m.group(1)
                continue
            m = INCBIN.match(linha)
            if m:
                blocos.append({
                    "arquivo": path.name, "linha": i, "rotulo": label,
                    "off": int(m.group(1), 16), "size": int(m.group(2), 16),
                    "texto": linha.strip(),
                })

    print("=" * 72)
    print("COMO CADA PONTEIRO APARECE EM data/*.s")
    print("=" * 72)

    isolados = []
    dentro_de_bloco = []
    for p in ponteiros:
        exato = [b for b in blocos if b["off"] == p and b["size"] == 4]
        if exato:
            isolados.append((p, exato[0]))
            continue
        contem = [b for b in blocos if b["off"] <= p < b["off"] + b["size"]]
        if contem:
            dentro_de_bloco.append((p, contem[0]))
        else:
            dentro_de_bloco.append((p, None))

    print(f"\n  com bloco proprio de 4 bytes: {len(isolados)}")
    print(f"  dentro de bloco maior       : {len(dentro_de_bloco)}")

    if dentro_de_bloco:
        print("\n  --- os que precisam de quebra ---")
        for p, b in dentro_de_bloco:
            if b is None:
                print(f"      0x{p:07X}: NAO ENCONTRADO em data/")
                continue
            print(f"      0x{p:07X}: dentro de {b['rotulo']} "
                  f"({b['arquivo']}:{b['linha']}, faixa 0x{b['off']:07X}"
                  f"..0x{b['off']+b['size']:07X}, {b['size']} bytes, "
                  f"offset +{p - b['off']})")
            print(f"          {b['texto']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
