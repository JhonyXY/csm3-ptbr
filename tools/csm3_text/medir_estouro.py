#!/usr/bin/env python3
"""Alguma linha traduzida estoura o byte de largura?

O renderizador guarda a largura da LINHA em [gUnk_03005180 + i*28 + 2], que e um
BYTE - teto de 255px. Em japones cada caractere ocupa 12px e a linha tinha no
maximo ~20 caracteres, entao dava 240px e cabia raspando. Em portugues sao ~1,7x
mais caracteres; mesmo com o VWF a 8,34px, uma linha de 31 caracteres ja passa de
255 e o byte da a volta.

Mede a largura real de cada linha traduzida com a tabela de larguras que a build
usa, e conta quantas passam.
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

TETO_BYTE = 255
TELA = 240


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    h, _ = fontmod.read_font_header(rom)
    tabela = (OUT / "larguras.bin").read_bytes()
    count = len(tabela)

    # caractere -> avanco em pixels, pela mesma tabela que o jogo usa
    largura_de = {}
    for faixa_lo, base in ((0x8260, "A"), (0x8281, "a"), (0x824F, "0")):
        n = 26 if base.isalpha() else 10
        for i in range(n):
            ch = chr(ord(base) + i)
            idx = fontmod.sjis_to_glyph_index(rom, faixa_lo + i)
            if idx is not None and idx < count:
                largura_de[ch] = tabela[idx]
    for ch, code in ((" ", 0x8140), ("?", 0x8148), ("!", 0x8149),
                     (",", 0x8143), (".", 0x8144), ("-", 0x815D),
                     (":", 0x8146), (";", 0x8147), ("'", 0x8166)):
        idx = fontmod.sjis_to_glyph_index(rom, code)
        if idx is not None and idx < count:
            largura_de[ch] = tabela[idx]

    mapa = json.loads((OUT / "acentos_mapa.json").read_text(encoding="utf-8"))
    for ch, hexcode in mapa.items():
        idx = fontmod.sjis_to_glyph_index(rom, int(hexcode, 16))
        if idx is not None and idx < count:
            largura_de[ch] = tabela[idx]

    media = sum(largura_de.values()) / len(largura_de)

    def medir(texto: str) -> int:
        return int(round(sum(largura_de.get(c, media) for c in texto)))

    dados = json.loads((OUT / "traducao.json").read_text(encoding="utf-8"))
    linhas = []
    for e in dados.get("traducoes", []):
        pt = (e.get("pt") or "").strip()
        if not pt or e.get("erro"):
            continue
        # O jogo quebra por linha; o texto pode trazer quebras explicitas.
        for linha in pt.split("\n"):
            if linha.strip():
                linhas.append((medir(linha), linha, e.get("jp", "")))

    linhas.sort(reverse=True)
    estouram = [l for l in linhas if l[0] > TETO_BYTE]
    passam_tela = [l for l in linhas if l[0] > TELA]

    print("=" * 74)
    print("LARGURA DAS LINHAS TRADUZIDAS")
    print("=" * 74)
    print(f"  linhas medidas          : {len(linhas):,}")
    print(f"  media                   : {sum(l[0] for l in linhas)/len(linhas):.0f}px")
    print(f"  maior                   : {linhas[0][0]}px")
    print()
    print(f"  passam da TELA ({TELA}px)  : {len(passam_tela):,} "
          f"({100*len(passam_tela)/len(linhas):.1f}%)")
    print(f"  ESTOURAM O BYTE ({TETO_BYTE}px): {len(estouram):,} "
          f"({100*len(estouram)/len(linhas):.1f}%)")
    print()

    if estouram:
        print("  As que estouram o byte (a largura da a volta e o jogo se perde):")
        for px, linha, jp in estouram[:10]:
            print(f"    {px:4d}px  {linha[:64]}")
        print()
        print("  CONFIRMA a suspeita: o campo de largura e u8 e essas linhas")
        print("  passam de 255px. E preciso quebrar a linha antes de injetar.")
    else:
        print("  Nenhuma linha passa de 255px - o byte de largura nao e a causa.")

    if passam_tela:
        print()
        print(f"  Linhas que passam da tela mas cabem no byte: "
              f"{len(passam_tela) - len(estouram):,}")
        print("  Essas nao travam, mas saem cortadas na horizontal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
