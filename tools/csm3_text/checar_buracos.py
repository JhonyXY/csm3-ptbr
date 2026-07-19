#!/usr/bin/env python3
"""Meu desenhador deixa colunas sem pintar entre uma letra e outra?

Hipotese: o original pinta 16px de fundo por glifo mas avanca 12, entao as
celulas se sobrepoem e TUDO fica pintado. O meu pinta so a largura do avanco -
se o avanco for menor que a area que o original cobria, sobram colunas
transparentes, que na tela viram buraco mostrando o cenario atras.

Simula uma linha inteira e conta as colunas que ficaram sem fundo.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import font as fontmod

REPO = Path(__file__).resolve().parents[2]
COR_FUNDO = 4
LARGURA_LINHA = 240
RESPIRO = 1


def largura_do_glifo(rows, w) -> int:
    if not any("#" in r for r in rows):
        return 4
    a, b = fontmod.ink_bounds(rows)
    return min(12, (b - a + 1) + RESPIRO)


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    h, _ = fontmod.read_font_header(rom)
    w, hh = h["width"], h["height"]
    data = rom[h["data_offset"]: h["data_offset"] + h["data_size"]]
    count = h["data_size"] // (fontmod.glyph_bytes_per_row(w) * hh)

    frase = "Salvar?"
    glifos = []
    for ch in frase:
        if "A" <= ch <= "Z":
            code = 0x8260 + (ord(ch) - ord("A"))
        elif "a" <= ch <= "z":
            code = 0x8281 + (ord(ch) - ord("a"))
        elif ch == "?":
            code = 0x8148
        else:
            continue
        idx = fontmod.sjis_to_glyph_index(rom, code)
        if idx is not None and idx < count:
            glifos.append(fontmod.decode_glyph(data, idx, w, hh))

    print("=" * 74)
    print("COLUNAS SEM FUNDO PINTADO")
    print("=" * 74)

    for nome, pinta_16, avanca_12 in (
            ("ORIGINAL: pinta 16px, avanca 12px", 16, True),
            ("MEU: pinta o avanco, avanca o avanco", None, False)):
        pintadas = set()
        x = 0
        for rows in glifos:
            avanco = 12 if avanca_12 else largura_do_glifo(rows, w)
            largura_pintada = pinta_16 if pinta_16 else avanco
            for c in range(x, x + largura_pintada):
                pintadas.add(c)
            x += avanco

        buracos = [c for c in range(x) if c not in pintadas]
        print(f"\n  {nome}")
        print(f"      largura total : {x}px")
        print(f"      colunas pintadas: {len(pintadas)}")
        print(f"      BURACOS       : {len(buracos)}")
        if buracos:
            print(f"      nas colunas   : {buracos[:20]}")

    print()
    print("=" * 74)
    print("CONCLUSAO")
    print("=" * 74)
    print("  Se o meu deixa buracos, a correcao e pintar SEMPRE 16px de fundo")
    print("  (como o original) e so DESENHAR a largura util. Pintar e desenhar")
    print("  sao coisas diferentes - eu tinha juntado as duas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
