#!/usr/bin/env python3
"""Imprime a nota COMPLETA dos opcodes indicados (o opcodes.json trunca em 400
caracteres; o resultado bruto do workflow tem o texto inteiro)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

OUT = Path(__file__).parent / "_out"
OPCODE_RE = re.compile(r"hi=0x([0-9A-Fa-f]{2})\[0x([0-9A-Fa-f]{2})\]")

alvos = [int(a, 16) for a in sys.argv[1:]] or [
    0x0440, 0x0460, 0x040C, 0x0001, 0x0461, 0x0453, 0x0361, 0x0360, 0x038C, 0x0202
]

raw = json.loads((OUT / "workflow_result.json").read_text(encoding="utf-8"))
data = raw.get("result", raw)

por_opcode: dict[int, list] = {}
for h in data.get("handlers", []):
    for e in h.get("opcodes", []) or []:
        m = OPCODE_RE.search(e)
        if m:
            code = (int(m.group(1), 16) << 8) | int(m.group(2), 16)
            por_opcode.setdefault(code, []).append(h)

for code in alvos:
    entries = por_opcode.get(code, [])
    print("=" * 74)
    print(f"OPCODE 0x{code:04X}")
    print("=" * 74)
    if not entries:
        print("  (nenhum handler mapeia para este opcode)")
        continue
    for h in entries:
        print(f"  handler {h.get('addr')} | operand_words={h.get('operand_words')} "
              f"| jump={h.get('is_jump')} texto={h.get('is_text')} "
              f"conf={h.get('confidence')}")
        print(f"  NOTA: {h.get('operand_note', '')}")
        print()
