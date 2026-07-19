#!/usr/bin/env python3
"""A tabela de larguras conhece os glifos acentuados?

gerar_larguras.py le a FONTE DA BASEROM. Os acentos, porem, sao gravados em
data1.s por patch_acentos.py - eles NAO existem na baserom. Se o slot estiver
vazio la, a tabela diz "largura de tinta = 0" e o desenhador nao pinta coluna
nenhuma: o acento vira um espaco.

Compara, para cada glifo acentuado, o que a baserom tem com o que a tabela diz.
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
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    h, _ = fontmod.read_font_header(rom)
    w, hh = h["width"], h["height"]
    dados = rom[h["data_offset"]: h["data_offset"] + h["data_size"]]
    count = h["data_size"] // (fontmod.glyph_bytes_per_row(w) * hh)

    tabela = (OUT / "larguras.bin").read_bytes()
    mapa = json.loads((OUT / "acentos_mapa.json").read_text(encoding="utf-8"))

    print("=" * 74)
    print("LARGURA DOS GLIFOS ACENTUADOS (tabela gerada da BASEROM)")
    print("=" * 74)
    print(f"  {'ch':3s} {'SJIS':6s} {'glifo':6s} {'tinta na baserom':17s} {'avanco':7s}")
    print("  " + "-" * 56)

    vazios = 0
    for ch, hexcode in mapa.items():
        codigo = int(hexcode, 16)
        idx = fontmod.sjis_to_glyph_index(rom, codigo)
        if idx is None or idx >= count:
            print(f"  {ch:3s} {hexcode:6s} sem glifo")
            continue
        linhas = fontmod.decode_glyph(dados, idx, w, hh)
        pixels = sum(r.count("#") for r in linhas)
        avanco = tabela[idx] if idx < len(tabela) else -1
        estado = "VAZIO" if pixels == 0 else f"{pixels} px"
        if pixels == 0:
            vazios += 1
        print(f"  {ch:3s} {hexcode:6s} {idx:6d} {estado:17s} {avanco:7d}")

    print()
    print("=" * 74)
    if vazios:
        print(f"  {vazios} de {len(mapa)} slots estao VAZIOS na baserom.")
        print("  A tabela foi feita a partir deles, entao manda desenhar zero")
        print("  colunas - o acento sai como espaco em branco. A tabela precisa")
        print("  ser gerada com os bitmaps ja acentuados.")
    else:
        print("  Todos os slots tem tinta na baserom: a largura sai plausivel")
        print("  e a causa do acento sumido e outra.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
