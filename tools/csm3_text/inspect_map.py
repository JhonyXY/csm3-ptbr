#!/usr/bin/env python3
"""Mostra as notas dos opcodes criticos (salto e texto) e os candidatos extras
achados pela varredura de completude."""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).parent / "_out"

opcodes = json.loads((OUT / "opcodes.json").read_text(encoding="utf-8"))
raw = json.loads((OUT / "workflow_result.json").read_text(encoding="utf-8"))
data = raw.get("result", raw)

print("=" * 72)
print("NOTAS DOS OPCODES DE SALTO")
print("=" * 72)
for key, spec in sorted(opcodes.items()):
    if spec["jump"]:
        print(f"\n  --- {key} ({spec['addr']}) ---")
        print(f"      operandos={spec['operands']} variavel={spec['variable']} "
              f"expressoes={spec['expressions']} alvo=op[{spec['jump_operand']}]")
        print(f"      {spec['note'][:340]}")

print()
print("=" * 72)
print("NOTAS DOS OPCODES DE TEXTO SEM CONTAGEM DE EXPRESSAO")
print("=" * 72)
for key, spec in sorted(opcodes.items()):
    if spec["text"] and not spec["expressions"]:
        print(f"\n  --- {key} ({spec['addr']}) ---")
        print(f"      {spec['note'][:340]}")

print()
print("=" * 72)
print("CANDIDATOS EXTRAS DA VARREDURA DE COMPLETUDE")
print("=" * 72)
extras = data.get("candidatos_extras", [])
seen = set()
for c in extras:
    addr = c.get("addr")
    if addr in seen:
        continue
    seen.add(addr)
    ops = ", ".join(c.get("opcodes", []) or [])
    print(f"\n  --- {addr}  [{ops}]  conf={c.get('confidence')} ---")
    print(f"      motivo: {(c.get('reason') or '')[:220]}")
    print(f"      prova : {(c.get('evidence') or '')[:260]}")

print()
print(f"  candidatos distintos: {len(seen)} (de {len(extras)} reportes)")
