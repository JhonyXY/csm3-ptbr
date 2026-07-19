#!/usr/bin/env python3
"""Consolida as sequencias ordenadas em _out/sequences.json.

Diferente da primeira passada, aqui cada handler devolve a ORDEM exata dos
elementos que consome (word / expr / string), que e o que o walker precisa.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

OUT = Path(__file__).parent / "_out"
RESULT = OUT / "workflow_seq.json"
SEQUENCES = OUT / "sequences.json"

OPCODE_RE = re.compile(r"hi=0x([0-9A-Fa-f]{2})\[0x([0-9A-Fa-f]{2})\]")
VALID = {"word", "expr", "string"}


def parse_opcodes(entries) -> list[int]:
    out = []
    for e in entries or []:
        m = OPCODE_RE.search(e)
        if m:
            out.append((int(m.group(1), 16) << 8) | int(m.group(2), 16))
    return out


def main() -> int:
    raw = json.loads(RESULT.read_text(encoding="utf-8"))
    data = raw.get("result", raw)
    handlers = data.get("handlers", [])

    for line in raw.get("logs", []) or []:
        print(f"  log: {line}")

    print("=" * 72)
    print("SEQUENCIAS EXTRAIDAS")
    print("=" * 72)
    print(f"  handlers            : {len(handlers)}")
    print(f"  com offset de codigo: {len(data.get('com_offset_de_codigo', []))}")
    print(f"  confianca baixa     : {len(data.get('confianca_baixa', []))}")

    conf = Counter(h.get("confidence", "?") for h in handlers)
    verif = sum(1 for h in handlers if h.get("verificado"))
    print(f"  confianca           : {dict(conf)}")
    print(f"  passaram pelo cetico: {verif}")

    opcodes: dict[str, dict] = {}
    conflicts = []
    invalid = []
    sem_opcode = []

    for h in handlers:
        codes = parse_opcodes(h.get("opcodes"))
        if not codes:
            sem_opcode.append(h.get("addr"))
            continue

        seq = h.get("sequence") or []
        if any(s not in VALID for s in seq):
            invalid.append((h.get("addr"), seq))
            continue

        jf = (h.get("jump_from") or "none").strip().lower()
        if jf in ("none", "", "null"):
            jf = None

        spec = {
            "addr": h.get("addr"),
            "seq": list(seq),
            "jump_from": jf,
            "confidence": h.get("confidence", "?"),
            "verificado": bool(h.get("verificado")),
        }

        for code in codes:
            key = f"0x{code:04X}"
            prev = opcodes.get(key)
            if prev and (prev["seq"] != spec["seq"] or prev["jump_from"] != spec["jump_from"]):
                conflicts.append((key, prev, spec))
                # Mantem o de maior confianca / verificado.
                score = lambda s: (s["verificado"], s["confidence"] == "alta")
                if score(spec) <= score(prev):
                    continue
            opcodes[key] = spec

    print()
    print(f"  opcodes mapeados : {len(opcodes)}")
    print(f"  handlers sem opcode: {len(sem_opcode)}")
    print(f"  sequencias invalidas: {len(invalid)}")
    print(f"  conflitos        : {len(conflicts)}")
    for key, a, b in conflicts[:6]:
        print(f"      {key}: {a['addr']} {a['seq']} vs {b['addr']} {b['seq']}")

    shapes = Counter(",".join(s["seq"]) or "(vazio)" for s in opcodes.values())
    print()
    print("  formatos mais comuns:")
    for shape, n in shapes.most_common(12):
        print(f"      [{shape}]: {n}")

    com_salto = {k: s for k, s in opcodes.items() if s["jump_from"]}
    print()
    print("=" * 72)
    print(f"OPCODES COM OFFSET DE CODIGO ({len(com_salto)}) - exigem relocacao")
    print("=" * 72)
    for key, s in sorted(com_salto.items()):
        seq = ",".join(s["seq"]) or "(vazio)"
        print(f"  {key}  seq=[{seq}]  alvo={s['jump_from']}  "
              f"conf={s['confidence']}  {s['addr']}")

    com_texto = {k: s for k, s in opcodes.items() if "string" in s["seq"]}
    print()
    print("=" * 72)
    print(f"OPCODES DE TEXTO ({len(com_texto)})")
    print("=" * 72)
    for key, s in sorted(com_texto.items()):
        seq = ",".join(s["seq"])
        marca = "  <-- TAMBEM tem offset de codigo" if s["jump_from"] else ""
        print(f"  {key}  seq=[{seq}]  conf={s['confidence']}{marca}")

    SEQUENCES.write_text(
        json.dumps(dict(sorted(opcodes.items())), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print()
    print(f"  gravado: {SEQUENCES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
