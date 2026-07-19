#!/usr/bin/env python3
"""Mapa exato das diferencas entre a ROM original e a traduzida.

Agrupa os bytes alterados em faixas contiguas e diz o que cada faixa e.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom

REPO = Path(__file__).resolve().parents[2]

BASE2 = csm3rom.ARCHIVE_OFFSETS[2]
FREE = 0x1FBB1ED
SYS_TABLE = 0x0BC9EC8
SYS_TABLE_FIM = SYS_TABLE + 43 * 4


def classify(start: int, end: int) -> str:
    tabela_fim = BASE2 + 8 + 3921 * 8
    if SYS_TABLE <= start < SYS_TABLE_FIM:
        n = (min(end, SYS_TABLE_FIM) - start + 3) // 4
        return f"tabela de ponteiros das strings de sistema ({n} entradas)"
    if BASE2 <= start < tabela_fim:
        idx = (start - BASE2 - 8) // 8
        return f"tabela do archive 2, entrada {idx}"
    if start >= FREE:
        return "regiao livre no fim da ROM (blob + strings realocados)"
    if BASE2 <= start < csm3rom.ARCHIVE_OFFSETS[1]:
        return "payload do archive 2"
    return "!!! FORA DO ESPERADO"


def main() -> int:
    orig = csm3rom.load_rom(REPO / "baserom.gba")
    nova = csm3rom.load_rom(REPO / "csm3_ptbr.gba")

    faixas = []
    inicio = None
    for i, (a, b) in enumerate(zip(orig, nova)):
        if a != b:
            if inicio is None:
                inicio = i
        elif inicio is not None:
            faixas.append((inicio, i))
            inicio = None
    if inicio is not None:
        faixas.append((inicio, len(orig)))

    # Junta faixas separadas por lacunas pequenas (bytes que coincidiram).
    fundidas = []
    for f in faixas:
        if fundidas and f[0] - fundidas[-1][1] <= 64:
            fundidas[-1] = (fundidas[-1][0], f[1])
        else:
            fundidas.append(f)

    print("=" * 72)
    print("MAPA DE DIFERENCAS")
    print("=" * 72)
    total = 0
    for start, end in fundidas:
        n = end - start
        total += n
        print(f"  0x{start:07X}..0x{end:07X}  {n:7,d} bytes  {classify(start, end)}")

    print()
    print(f"  faixas alteradas : {len(fundidas)}")
    print(f"  bytes alterados  : {total:,} de {len(orig):,} "
          f"({100*total/len(orig):.4f}%)")

    inesperadas = [f for f in fundidas if "FORA DO ESPERADO" in classify(*f)]
    print()
    if inesperadas:
        print(f"  ATENCAO: {len(inesperadas)} faixa(s) fora do esperado")
        return 1
    print("  Todas as faixas sao esperadas: tabela do archive + blob realocado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
