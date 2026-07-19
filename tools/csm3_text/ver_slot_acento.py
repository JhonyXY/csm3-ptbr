#!/usr/bin/env python3
"""Os slots onde os acentos foram gravados tem tinta na BASEROM?

A tabela de larguras e indexada por INDICE DE GLIFO e gerada a partir da
baserom. patch_acentos.py sobrescreve o BITMAP desses slots com as acentuadas,
mas a tabela ja foi feita com o conteudo antigo. Se o slot era vazio, a tabela
diz "tinta = 0" e o desenhador nao pinta coluna nenhuma.

'a com til' e o glifo 311 na ROM construida (medido por ver_acentos.py).
"""

from __future__ import annotations

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
    tabela = (OUT / "larguras.bin").read_bytes()

    print("=" * 66)
    print("SLOTS 306-333 NA BASEROM  (os acentos ocupam 308 em diante)")
    print("=" * 66)
    print("  glifo  tinta_na_baserom  avanco_na_tabela")
    vazios = []
    for i in range(306, 334):
        linhas = fontmod.decode_glyph(dados, i, w, hh)
        px = sum(r.count("#") for r in linhas)
        av = tabela[i] if i < len(tabela) else -1
        marca = "  <- VAZIO" if px == 0 else ""
        if px == 0:
            vazios.append(i)
        print(f"  {i:5d}  {px:16d}  {av:16d}{marca}")

    print()
    print("=" * 66)
    if vazios:
        print(f"  {len(vazios)} slots vazios: {vazios}")
        print("  A tabela manda desenhar 0 colunas neles. Como patch_acentos")
        print("  poe o bitmap acentuado depois, o glifo existe mas nao e")
        print("  pintado - o acento vira espaco em branco.")
        print("  CORRECAO: gerar a tabela com os bitmaps acentuados aplicados.")
    else:
        print("  Nenhum slot vazio - a largura sai plausivel e a causa e outra.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
