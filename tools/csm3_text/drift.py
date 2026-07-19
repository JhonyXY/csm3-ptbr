#!/usr/bin/env python3
"""Localiza a origem do drift do walker.

Quando o walker le uma palavra que nao e opcode valido, o culpado quase sempre e
a instrucao ANTERIOR, cuja especificacao consumiu palavras demais ou de menos.
Este script cruza cada ponto de erro com o opcode que o precedeu, e ranqueia os
suspeitos.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import walker
from opcode_spec import CRITICAL

ROM_PATH = Path(__file__).resolve().parents[2] / "baserom.gba"

# Tamanho real de cada tabela de despacho (do survey.py).
TABLE_SIZES = {0x00: 16, 0x01: 23, 0x02: 88, 0x03: 143, 0x04: 168}


def is_plausible_opcode(op: int) -> bool:
    hi, lo = op >> 8, op & 0xFF
    size = TABLE_SIZES.get(hi)
    return size is not None and lo < size


def main() -> int:
    rom = csm3rom.load_rom(ROM_PATH)
    auto_map = walker.load_auto_map()

    predecessor = Counter()
    pred_detail = {}
    implausible = Counter()

    for script in csm3rom.iter_scripts(rom):
        body = bytes(script.body)
        result = walker.walk(body, auto_map)

        prev = None
        for ins in result.instructions:
            if not is_plausible_opcode(ins.opcode):
                implausible[ins.opcode] += 1
                if prev is not None:
                    predecessor[prev.opcode] += 1
                    pred_detail.setdefault(prev.opcode, []).append(
                        (script.index, prev.offset, prev.size, ins.opcode)
                    )
            prev = ins

    print("=" * 72)
    print("PALAVRAS LIDAS COMO OPCODE QUE NAO EXISTEM NAS TABELAS")
    print("=" * 72)
    print(f"  distintas: {len(implausible):,} | ocorrencias: {sum(implausible.values()):,}")
    for op, n in implausible.most_common(10):
        hi, lo = op >> 8, op & 0xFF
        size = TABLE_SIZES.get(hi, 0)
        print(f"      0x{op:04X}  hi=0x{hi:02X} idx=0x{lo:02X} (tabela tem {size})  {n:,}x")

    print()
    print("=" * 72)
    print("SUSPEITOS: opcode que PRECEDE o ponto de drift")
    print("=" * 72)
    print("  (a spec destes provavelmente consome palavras demais ou de menos)")
    print()
    for op, n in predecessor.most_common(20):
        origem = "MANUAL" if op in CRITICAL else "auto"
        entry = auto_map.get(op, {})
        spec = walker.opcode_spec.spec_for(op, auto_map) or {}
        seq = ",".join(spec.get("seq", [])) or "(vazio)"
        print(
            f"  0x{op:04X}  {n:5,d}x drift  | spec={origem} seq=[{seq}] "
            f"var={entry.get('variable')} expr={entry.get('expressions')} "
            f"conf={entry.get('confidence')}"
        )
        exemplos = pred_detail[op][:2]
        for sidx, off, size, badop in exemplos:
            print(
                f"          ex: script {sidx} @0x{off:04X} tamanho {size}B "
                f"-> leu 0x{badop:04X}"
            )
        nota = entry.get("note", "")
        if nota:
            print(f"          nota: {nota[:160]}")

    print()
    print("=" * 72)
    print("RESUMO")
    print("=" * 72)
    top = predecessor.most_common(5)
    coberto = sum(n for _, n in top)
    total = sum(predecessor.values())
    if total:
        print(f"  os 5 piores suspeitos respondem por {coberto:,} de {total:,} "
              f"drifts ({100*coberto/total:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
