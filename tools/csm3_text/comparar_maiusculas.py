#!/usr/bin/env python3
"""Compara maiuscula normal contra acentuada, para ver se cortou embaixo.

As maiusculas ocupam as linhas 1-9 (so 1 linha livre em cima). Com acento de
3 linhas mais 1 de respiro, a letra desce 3 - e pode perder o rodape.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import font as fontmod

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"


def main() -> int:
    rom = csm3rom.load_rom(REPO / "csm3.gba")
    h, _ = fontmod.read_font_header(rom)
    w, hh = h["width"], h["height"]
    data = rom[h["data_offset"]: h["data_offset"] + h["data_size"]]
    count = h["data_size"] // (fontmod.glyph_bytes_per_row(w) * hh)
    mapa = json.loads((OUT / "acentos_mapa.json").read_text(encoding="utf-8"))

    pares = [("A", "Á"), ("A", "Ã"), ("E", "É"), ("O", "Õ"), ("C", "Ç")]

    for base, acentuada in pares:
        sjis_base = 0x8260 + (ord(base) - ord("A"))
        i_base = fontmod.sjis_to_glyph_index(rom, sjis_base)
        i_ac = fontmod.sjis_to_glyph_index(rom, int(mapa[acentuada], 16))
        if i_base is None or i_ac is None or i_base >= count or i_ac >= count:
            print(f"  {base}/{acentuada}: sem glifo")
            continue

        rb = fontmod.decode_glyph(data, i_base, w, hh)
        ra = fontmod.decode_glyph(data, i_ac, w, hh)

        print(f"\n  '{base}' normal          '{acentuada}' acentuada")
        for y in range(hh):
            print(f"      {rb[y]}    {ra[y]}")

        # Conta pixels: se a acentuada tiver MENOS tinta na letra, cortou.
        tinta_base = sum(r.count("#") for r in rb)
        tinta_ac = sum(r.count("#") for r in ra)
        acento_esperado = 6 if acentuada in "ÁÀÉÍÓÚ" else 5
        perda = tinta_base + acento_esperado - tinta_ac
        estado = "OK" if perda <= 1 else f"CORTOU ~{perda} pixels"
        print(f"      tinta: base {tinta_base}, acentuada {tinta_ac}  -> {estado}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
