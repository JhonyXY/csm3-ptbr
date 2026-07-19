#!/usr/bin/env python3
"""Mostra o resultado do piloto lado a lado, para avaliar qualidade."""

from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = Path(__file__).parent / "_out"
arquivo = sys.argv[1] if len(sys.argv) > 1 else "piloto.json"

d = json.loads((OUT / arquivo).read_text(encoding="utf-8"))
trads = d["traducoes"]

print("=" * 76)
print(f"PILOTO - {len(trads)} falas")
print("=" * 76)

for t in trads:
    marca = ""
    if t.get("erro"):
        marca = f"  [REJEITADA: {t['erro']}]"
    elif t["chars_pt"] > 54:
        marca = f"  [{t['chars_pt']} chars - estoura a caixa de 54]"
    print(f"\n  jp ({t['chars_jp']:2d}): {t['jp']}")
    print(f"  pt ({t['chars_pt']:2d}): {t['pt']}{marca}")

validas = [t for t in trads if not t.get("erro") and t["chars_jp"]]
if validas:
    exp = sum(t["chars_pt"] for t in validas) / sum(t["chars_jp"] for t in validas)
    print()
    print("=" * 76)
    print(f"  expansao: {exp:.2f}x")
    print(f"  mais longa: {max(t['chars_pt'] for t in validas)} chars")
    acima = [t for t in validas if t["chars_pt"] > 54]
    print(f"  acima de 54 chars: {len(acima)}/{len(validas)}")
    print(f"  acima de 78 (com VWF): "
          f"{sum(1 for t in validas if t['chars_pt'] > 78)}/{len(validas)}")
