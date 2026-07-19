#!/usr/bin/env python3
"""Procura "Nao" e "Nao com til" na ROM construida, pelos bytes.

As strings traduzidas sao reapontadas para outro lugar, entao olhar o endereco
original nao serve. Esta busca varre a ROM inteira.

Codificacao do jogo (SJIS de largura dupla, gravado em little-endian):
    'N' = 0x826D    'a' = 0x8281    'o' = 0x828F    'til-a' = 0x8443
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom

REPO = Path(__file__).resolve().parents[2]


def cod(c: str) -> int:
    if "A" <= c <= "Z":
        return 0x8260 + ord(c) - ord("A")
    if "a" <= c <= "z":
        return 0x8281 + ord(c) - ord("a")
    raise ValueError(c)


def seq(*codigos) -> bytes:
    return b"".join(c.to_bytes(2, "little") for c in codigos)


def main() -> int:
    rom = csm3rom.load_rom(REPO / "csm3.gba")

    alvos = {
        "Nao  (sem til)": seq(cod("N"), cod("a"), cod("o")),
        "Nao com til":    seq(cod("N"), 0x8443, cod("o")),
        "Sim":            seq(cod("S"), cod("i"), cod("m")),
        "Salvar":         seq(cod("S"), cod("a"), cod("l"), cod("v"),
                              cod("a"), cod("r")),
    }

    print("=" * 74)
    print("BUSCA POR BYTES NA ROM CONSTRUIDA")
    print("=" * 74)
    for nome, padrao in alvos.items():
        pos = []
        i = rom.find(padrao)
        while i >= 0 and len(pos) < 6:
            pos.append(i)
            i = rom.find(padrao, i + 2)
        marca = " <<<" if pos else ""
        print(f"  {nome:16s} {padrao.hex():26s} {len(pos)} ocorrencia(s){marca}")
        for p in pos[:4]:
            print(f"      offset {p:#010x}  (endereco {0x08000000 + p:#010x})")

    # Quantos codigos de acento existem na ROM inteira?
    print()
    print("  --- uso de codigos acentuados na ROM ---")
    total = 0
    for codigo in range(0x8440, 0x8459):
        padrao = codigo.to_bytes(2, "little")
        n = rom.count(padrao)
        total += n
    print(f"  ocorrencias de qualquer codigo 0x8440-0x8458: {total:,}")
    print("  (inclui coincidencias em dados binarios, mas zero seria decisivo)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
