#!/usr/bin/env python3
"""Descobre onde o desenhador original poe a sombra.

Acende UM pixel e decodifica todo o buffer de volta em (linha, coluna, cor).
Assim o deslocamento da sombra sai medido, nao suposto - foi supor isso que
manteve o desenhador novo divergindo.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
from mapear_destino import DESTINO, GLIFO_FALSO, glifo_um_pixel
from thumb import Cpu, Memoria

REPO = Path(__file__).resolve().parents[2]
BLIT_FASE0 = 0x08003BC0
BLIT_FASE4 = 0x08003EB8


def endereco(coluna: int, linha: int) -> int:
    return ((coluna >> 3) * 0x40 + (linha >> 3) * 0x20
            + (linha & 7) * 4 + ((coluna & 7) >> 1))


def decodificar(buf: bytes) -> dict[tuple[int, int], int]:
    """Devolve {(linha, coluna): cor} para tudo que estiver aceso."""
    saida = {}
    for linha in range(16):
        for coluna in range(16):
            i = endereco(coluna, linha)
            if i >= len(buf):
                continue
            b = buf[i]
            cor = (b >> 4) if (coluna & 1) else (b & 0x0F)
            if cor:
                saida[(linha, coluna)] = cor
    return saida


def rodar(rom: bytes, glifo: bytes, fase: int) -> bytes:
    mem = Memoria()
    mem.mapear(0x08000000, rom)
    mem.mapear(0x02000000, bytes(0x20000))
    mem.mapear(0x03000000, bytes(0x8000))
    dados, off = mem._achar(GLIFO_FALSO, len(glifo))
    dados[off:off + len(glifo)] = glifo
    cpu = Cpu(mem)
    cpu.r[0], cpu.r[1], cpu.r[2], cpu.r[3] = GLIFO_FALSO, DESTINO, 0, 0
    cpu.r[13] = 0x03007F00
    cpu.executar(fase)
    buf, base = mem._achar(DESTINO, 0x100)
    return bytes(buf[base:base + 0x100])


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")

    print("=" * 74)
    print("ONDE A SOMBRA CAI (um pixel aceso por vez)")
    print("=" * 74)

    for linha_teste, coluna_teste in ((0, 0), (3, 3), (5, 5), (0, 8), (11, 11)):
        saida = decodificar(rodar(rom, glifo_um_pixel(linha_teste, coluna_teste),
                                  BLIT_FASE0))
        print(f"\n  pixel aceso em (linha {linha_teste}, coluna {coluna_teste}):")
        for (l, c), cor in sorted(saida.items()):
            desloc = f"({l - linha_teste:+d}, {c - coluna_teste:+d})"
            papel = {1: "tinta", 2: "sombra", 3: "tinta+sombra"}.get(cor, f"cor {cor}")
            print(f"      linha {l:2d} col {c:2d}  cor {cor}  {desloc:>10}  {papel}")

    # Consolida: qual e o deslocamento da sombra?
    print()
    print("=" * 74)
    print("CONSOLIDADO")
    print("=" * 74)
    deslocamentos = {}
    for linha_teste in range(1, 10):
        for coluna_teste in range(1, 10):
            saida = decodificar(rodar(rom, glifo_um_pixel(linha_teste, coluna_teste),
                                      BLIT_FASE0))
            for (l, c), cor in saida.items():
                d = (l - linha_teste, c - coluna_teste)
                deslocamentos.setdefault(cor, set()).add(d)

    for cor in sorted(deslocamentos):
        papel = {1: "tinta", 2: "sombra", 3: "tinta+sombra"}.get(cor, f"cor {cor}")
        ds = sorted(deslocamentos[cor])
        print(f"  cor {cor} ({papel}): deslocamentos {ds}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
