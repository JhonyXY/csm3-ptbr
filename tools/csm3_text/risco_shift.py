#!/usr/bin/env python3
"""Mede o risco de deixar o linker deslocar os dados.

Se um bloco de data/ crescer, tudo depois dele anda. Referencias SIMBOLICAS o
linker corrige; ponteiros CRUS dentro dos .incbin, nao.

Este script conta quantos ponteiros crus existem na ROM apontando para depois de
um ponto de corte - ou seja, quantos quebrariam.
"""

from __future__ import annotations

import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom

REPO = Path(__file__).resolve().parents[2]

# Primeira string de sistema: se ela crescer, tudo a partir daqui desloca.
CORTE = 0x00BADCC


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    n = len(rom)

    print("=" * 72)
    print(f"PONTEIROS QUE QUEBRARIAM SE O DADO EM 0x{CORTE:07X} CRESCESSE")
    print("=" * 72)

    alvo_min = 0x08000000 + CORTE
    alvo_max = 0x08000000 + n

    total_ptr = 0
    afetados = 0
    por_regiao = Counter()

    # Varre a ROM inteira em passos de 4 (alinhamento tipico de ponteiro).
    for off in range(0, n - 4, 4):
        val = struct.unpack_from("<I", rom, off)[0]
        if not (0x08000000 <= val < alvo_max):
            continue
        total_ptr += 1
        if val >= alvo_min:
            afetados += 1
            # de onde parte o ponteiro?
            if off < 0x0BB0000:
                por_regiao["codigo/dados iniciais"] += 1
            elif off < csm3rom.ARCHIVE_OFFSETS[2]:
                por_regiao["dados intermediarios"] += 1
            else:
                por_regiao["archives"] += 1

    print(f"  ponteiros GBA plausiveis na ROM inteira : {total_ptr:,}")
    print(f"  apontando para DEPOIS do corte          : {afetados:,}")
    print()
    print("  origem dos afetados:")
    for regiao, qtd in por_regiao.most_common():
        print(f"      {regiao}: {qtd:,}")

    print()
    print("=" * 72)
    print("VEREDITO")
    print("=" * 72)
    if afetados > 100:
        print(f"  {afetados:,} ponteiros crus quebrariam. Deixar o linker deslocar")
        print("  os dados EXISTENTES nao e viavel neste repo - eles sao bytes")
        print("  opacos, nao referencias simbolicas.")
        print()
        print("  Solucao: NAO mexer no que existe. Colocar as strings novas em um")
        print("  arquivo NOVO, adicionado ao FINAL da secao rom no linker.ld.")
        print("  Assim nada desloca, e os ponteiros viram .4byte simbolico que o")
        print("  linker resolve para o endereco final.")
    else:
        print(f"  So {afetados} ponteiros afetados - deslocar seria viavel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
