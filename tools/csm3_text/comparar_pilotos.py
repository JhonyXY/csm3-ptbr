#!/usr/bin/env python3
"""Compara os dois pilotos: com e sem a capacidade extra que o VWF daria.

Este e o experimento que decide se o VWF e necessario ou opcional.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).parent / "_out"


def carregar(nome: str) -> list[dict]:
    d = json.loads((OUT / nome).read_text(encoding="utf-8"))
    return [t for t in d["traducoes"] if not t.get("erro") and t["chars_jp"]]


a = carregar("p54.json")   # sem VWF: 54 chars por caixa
b = carregar("p78.json")   # com VWF: 78 chars por caixa

print("=" * 74)
print("SEM VWF (54 chars/caixa)  x  COM VWF (78 chars/caixa)")
print("=" * 74)

for nome, dados, cap in (("sem VWF", a, 54), ("com VWF", b, 78)):
    if not dados:
        print(f"\n  {nome}: sem dados")
        continue
    exp = sum(t["chars_pt"] for t in dados) / sum(t["chars_jp"] for t in dados)
    estoura = [t for t in dados if t["chars_pt"] > cap]
    print(f"\n  {nome}  ({len(dados)} falas)")
    print(f"      expansao          : {exp:.2f}x")
    print(f"      estouram a caixa  : {len(estoura)} ({100*len(estoura)/len(dados):.0f}%)")
    print(f"      mais longa        : {max(t['chars_pt'] for t in dados)} chars")

# Lado a lado, so onde as duas versoes existem.
por_id_a = {t["id"]: t for t in a}
por_id_b = {t["id"]: t for t in b}
comuns = [i for i in por_id_a if i in por_id_b
          and por_id_a[i]["pt"] != por_id_b[i]["pt"]]

print()
print("=" * 74)
print("ONDE O APERTO MUDOU A TRADUCAO")
print("=" * 74)
for i in comuns[:8]:
    ta, tb = por_id_a[i], por_id_b[i]
    print(f"\n  jp: {ta['jp']}")
    print(f"  54: {ta['pt']}  ({ta['chars_pt']})")
    print(f"  78: {tb['pt']}  ({tb['chars_pt']})")

print()
print("=" * 74)
print("VEREDITO")
print("=" * 74)
if a and b:
    est_a = sum(1 for t in a if t["chars_pt"] > 54)
    est_b = sum(1 for t in b if t["chars_pt"] > 78)
    print(f"  Espremendo em 54 chars, {100*est_a/len(a):.0f}% ainda estoura -")
    print(f"  e o que cabe perde informacao (ver comparacoes acima).")
    print(f"  Com 78 chars, {100*est_b/len(b):.0f}% estoura.")
    print()
    if est_b * 4 < est_a:
        print("  => O VWF nao e estetica: e o que permite traduzir sem")
        print("     mutilar as falas longas.")
