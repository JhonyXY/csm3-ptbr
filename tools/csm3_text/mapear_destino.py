#!/usr/bin/env python3
"""Descobre o layout exato do buffer de destino do blitter.

Metodo: monta um glifo sintetico com UM unico pixel aceso, roda o blitter, e ve
qual byte mudou. Repetindo para cada (linha, coluna), sai o mapa completo -
medido, nao deduzido.

Com esse mapa da para escrever um blitter novo que desenhe so a largura util,
que e o que o VWF exige.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import font as fontmod
from thumb import Cpu, Memoria, ThumbError

REPO = Path(__file__).resolve().parents[2]

BLIT_FASE0 = 0x08003BC0
BLIT_FASE4 = 0x08003EB8
GLIFO_FALSO = 0x02005000    # onde ponho o glifo sintetico
DESTINO = 0x02010000
TAM_DESTINO = 0x200


def glifo_um_pixel(linha: int, coluna: int) -> bytes:
    """12 linhas de 2 bytes. Pixels 0-7 no byte 0 (MSB primeiro),
    pixels 8-11 no nibble alto do byte 1."""
    out = bytearray(24)
    if coluna < 8:
        out[linha * 2] = 0x80 >> coluna
    else:
        out[linha * 2 + 1] = 0x80 >> (coluna - 8)
    return bytes(out)


def rodar(rom: bytes, glifo: bytes, fase: int) -> dict[int, int]:
    mem = Memoria()
    mem.mapear(0x08000000, rom)
    mem.mapear(0x02000000, bytes(0x20000))
    mem.mapear(0x03000000, bytes(0x8000))
    dados, off = mem._achar(GLIFO_FALSO, len(glifo))
    dados[off:off + len(glifo)] = glifo

    cpu = Cpu(mem)
    cpu.r[0] = GLIFO_FALSO
    cpu.r[1] = DESTINO
    cpu.r[2] = 0
    cpu.r[3] = 0
    cpu.r[13] = 0x03007F00
    cpu.executar(fase)

    buf, base = mem._achar(DESTINO, TAM_DESTINO)
    return {i: buf[base + i] for i in range(TAM_DESTINO) if buf[base + i]}


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")

    print("=" * 74)
    print("MAPA DO BUFFER DE DESTINO (medido pixel a pixel)")
    print("=" * 74)

    for nome, fase in (("FASE 0", BLIT_FASE0), ("FASE 4", BLIT_FASE4)):
        print(f"\n{'-' * 74}")
        print(f"{nome}")
        print(f"{'-' * 74}")

        mapa: dict[tuple[int, int], list[int]] = {}
        for linha in range(12):
            for coluna in range(12):
                try:
                    tocados = rodar(rom, glifo_um_pixel(linha, coluna), fase)
                except ThumbError as exc:
                    print(f"  ERRO em ({linha},{coluna}): {exc}")
                    return 1
                if tocados:
                    mapa[(linha, coluna)] = sorted(tocados)

        # Por coluna: quais offsets ela usa?
        por_coluna: dict[int, set[int]] = defaultdict(set)
        for (linha, coluna), offs in mapa.items():
            por_coluna[coluna].update(offs)

        print("  coluna -> faixa de bytes que ela ocupa")
        for c in sorted(por_coluna):
            offs = sorted(por_coluna[c])
            print(f"      col {c:2d}: 0x{min(offs):03X}..0x{max(offs):03X} "
                  f"({len(offs)} bytes distintos)")

        # Por linha, na coluna 0: revela o passo vertical.
        col0 = {l: mapa.get((l, 0), []) for l in range(12)}
        print("\n  linha -> byte (coluna 0), revela o passo vertical")
        anterior = None
        for l in sorted(col0):
            if col0[l]:
                off = min(col0[l])
                passo = f"  (+{off - anterior})" if anterior is not None else ""
                print(f"      linha {l:2d}: 0x{off:03X}{passo}")
                anterior = off

        pixels_sem_efeito = [(l, c) for l in range(12) for c in range(12)
                             if (l, c) not in mapa]
        if pixels_sem_efeito:
            print(f"\n  pixels que NAO produziram escrita: {len(pixels_sem_efeito)}")
            print(f"      {pixels_sem_efeito[:12]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
