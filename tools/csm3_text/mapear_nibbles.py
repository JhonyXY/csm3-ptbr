#!/usr/bin/env python3
"""Descobre qual metade de cada byte corresponde a qual coluna de pixel.

Cada byte guarda DOIS pixels (4 bits cada). Preciso saber se a coluna par usa a
metade alta ou a baixa - errar isso espelha o texto. Descubro acendendo um pixel
de cada vez e olhando o valor que aparece.
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


def rodar(rom: bytes, glifo: bytes) -> dict[int, int]:
    mem = Memoria()
    mem.mapear(0x08000000, rom)
    mem.mapear(0x02000000, bytes(0x20000))
    mem.mapear(0x03000000, bytes(0x8000))
    dados, off = mem._achar(GLIFO_FALSO, len(glifo))
    dados[off:off + len(glifo)] = glifo
    cpu = Cpu(mem)
    cpu.r[0], cpu.r[1], cpu.r[2], cpu.r[3] = GLIFO_FALSO, DESTINO, 0, 0
    cpu.r[13] = 0x03007F00
    cpu.executar(BLIT_FASE0)
    buf, base = mem._achar(DESTINO, 0x100)
    return {i: buf[base + i] for i in range(0x100) if buf[base + i]}


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")

    print("=" * 74)
    print("QUAL METADE DO BYTE E CADA COLUNA (linha 0)")
    print("=" * 74)
    print(f"  {'coluna':>7}  {'byte':>6}  {'valor':>6}  metade")

    formula_ok = True
    for coluna in range(12):
        tocados = rodar(rom, glifo_um_pixel(0, coluna))
        if not tocados:
            print(f"  {coluna:7d}  (nenhuma escrita)")
            continue
        off, val = min(tocados.items())
        metade = "baixa" if (val & 0x0F) else "alta"
        # Formula que eu pretendo usar no blitter novo:
        prevista = (coluna // 8) * 0x40 + (coluna % 8) // 2
        marca = "" if prevista == off else f"  <-- formula previa 0x{prevista:03X}"
        print(f"  {coluna:7d}  0x{off:04X}  0x{val:02X}    {metade}{marca}")
        if prevista != off:
            formula_ok = False

    print()
    print("=" * 74)
    print("CONCLUSAO")
    print("=" * 74)
    if formula_ok:
        print("  A formula de endereco confere com a medicao:")
        print("      byte = (coluna//8)*0x40 + (linha//8)*0x20")
        print("             + (linha%8)*4 + (coluna%8)//2")
    else:
        print("  A formula NAO confere - revisar antes de escrever o blitter.")

    # Confere tambem o passo vertical com a formula completa.
    print()
    print("  verificando o passo vertical (coluna 0, todas as linhas):")
    erros = 0
    for linha in range(12):
        tocados = rodar(rom, glifo_um_pixel(linha, 0))
        if not tocados:
            continue
        off = min(tocados)
        prevista = (linha // 8) * 0x20 + (linha % 8) * 4
        estado = "ok" if prevista == off else f"DIVERGE (previa 0x{prevista:03X})"
        if prevista != off:
            erros += 1
        print(f"      linha {linha:2d}: 0x{off:03X}  {estado}")
    print(f"\n  divergencias: {erros}")
    return 0 if formula_ok and erros == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
