#!/usr/bin/env python3
"""Mostra uma amostra do JSON de traducao gerado."""

from __future__ import annotations

import json
import os
from pathlib import Path

OUT = Path(__file__).parent / "_out"
path = OUT / "textos_originais.json"

d = json.loads(path.read_text(encoding="utf-8"))
print(f"arquivo: {os.path.getsize(path)/1048576:.1f} MB")
print(f"strings: {d['_meta']['total_strings']:,} em {d['_meta']['scripts']:,} scripts")
print()

print("--- entrada de dialogo com placeholder de nome ---")
for e in d["strings"]:
    if "{g}" in e["jp"] and e["chars"] > 10:
        print(json.dumps(e, ensure_ascii=False, indent=2))
        break

tags = ("{g}", "{d}", "{z}", "{b}", "{e}", "{t}")
n = sum(1 for e in d["strings"] if any(t in e["jp"] for t in tags))
print()
print(f"--- entradas com placeholder de nome: {n:,} de {len(d['strings']):,} ---")

print()
print("--- distribuicao de tamanho (caracteres japoneses) ---")
buckets = {}
for e in d["strings"]:
    b = min(e["chars"] // 5 * 5, 40)
    buckets[b] = buckets.get(b, 0) + 1
for b in sorted(buckets):
    label = f"{b}-{b+4}" if b < 40 else "40+"
    bar = "#" * min(46, buckets[b] * 46 // max(buckets.values()))
    print(f"  {label:>6} chars: {buckets[b]:6,d}  {bar}")

longest = max(d["strings"], key=lambda e: e["chars"])
print()
print(f"--- string mais longa ({longest['chars']} chars) ---")
print(f"  {longest['jp']}")
