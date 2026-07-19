#!/usr/bin/env python3
"""Confere os bytes do desvio no inicio de sub_08001F14 na ROM construida."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom

REPO = Path(__file__).resolve().parents[2]
ENDERECO = 0x1F14  # offset na ROM de sub_08001F14


def main() -> int:
    base = csm3rom.load_rom(REPO / "baserom.gba")
    nova = csm3rom.load_rom(REPO / "csm3.gba")

    print("=" * 72)
    print(f"DESVIO EM sub_08001F14 (ROM 0x{ENDERECO:07X} / GBA 0x{0x08000000+ENDERECO:08X})")
    print("=" * 72)

    print("\n  --- original ---")
    for i in range(0, 12, 2):
        w = struct.unpack_from("<H", base, ENDERECO + i)[0]
        print(f"      +{i:2d}: {w:04X}")

    print("\n  --- com VWF ---")
    for i in range(0, 12, 2):
        w = struct.unpack_from("<H", nova, ENDERECO + i)[0]
        print(f"      +{i:2d}: {w:04X}")

    ldr = struct.unpack_from("<H", nova, ENDERECO)[0]
    bx = struct.unpack_from("<H", nova, ENDERECO + 2)[0]
    alvo = struct.unpack_from("<I", nova, ENDERECO + 4)[0]

    print()
    print("  --- decodificacao ---")
    print(f"      {ldr:04X}: ldr r3, [pc, #{(ldr & 0xFF) * 4}]"
          f"  {'OK' if (ldr & 0xF800) == 0x4800 else 'INESPERADO'}")
    print(f"      {bx:04X}: bx r3"
          f"  {'OK' if bx == 0x4718 else 'INESPERADO'}")
    print(f"      alvo: 0x{alvo:08X}  "
          f"{'thumb (bit 0 setado)' if alvo & 1 else 'ARM - ERRADO!'}")

    # O alvo tem que bater com o simbolo do mapa.
    mapa = REPO / "csm3.map"
    esperado = None
    if mapa.exists():
        for linha in mapa.read_text(encoding="utf-8", errors="replace").splitlines():
            if linha.strip().endswith("PtBrRenderizaTexto"):
                partes = linha.split()
                if partes and partes[0].startswith("0x"):
                    esperado = int(partes[0], 16)
                    break

    print()
    if esperado is not None:
        print(f"      PtBrRenderizaTexto no mapa: 0x{esperado:08X}")
        if alvo == esperado + 1:
            print("      O desvio aponta exatamente para a funcao nova. OK")
            resultado = 0
        else:
            print(f"      DIVERGE: esperava 0x{esperado+1:08X}")
            resultado = 1
    else:
        print("      simbolo nao encontrado no mapa")
        resultado = 1

    # A tabela de larguras esta acessivel e com conteudo?
    print()
    print("=" * 72)
    print("TABELA DE LARGURAS NA ROM")
    print("=" * 72)
    tab = None
    for linha in mapa.read_text(encoding="utf-8", errors="replace").splitlines():
        if linha.strip().endswith("gPtBrLarguras"):
            partes = linha.split()
            if partes and partes[0].startswith("0x"):
                tab = int(partes[0], 16) - 0x08000000
                break
    if tab:
        amostra = nova[tab:tab + 48]
        usados = [b for b in amostra[::3]]
        print(f"      offset ROM 0x{tab:07X}")
        print(f"      primeiras larguras (1=4px, 2=8px, 3=12px): {usados[:16]}")
        if all(1 <= u <= 3 for u in usados[:16]):
            print("      valores dentro da faixa esperada. OK")
        else:
            print("      valores fora da faixa - tabela suspeita")
            resultado = 1

    return resultado


if __name__ == "__main__":
    raise SystemExit(main())
