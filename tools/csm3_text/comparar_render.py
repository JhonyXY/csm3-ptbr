#!/usr/bin/env python3
"""O que exatamente o VWF degrada? Compara render original x VWF, pixel a pixel.

Eu disse "e a sombra recortada" sem medir. Isto renderiza a mesma frase pelos
dois caminhos e mostra a diferenca - se a perda for nas colunas de sombra, o
diagnostico se confirma; se for em outro lugar, era outra coisa.

Reproduz o desenhador em Python (ja validado 47/47 contra o original executado
no interpretador thumb).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import font as fontmod

REPO = Path(__file__).resolve().parents[2]
LARGURA = 160
ALTURA = 16
COR_TINTA = 1
COR_SOMBRA = 2
COR_FUNDO = 4


def glifo_de(rom, data, count, w, h, ch):
    if "A" <= ch <= "Z":
        code = 0x8260 + (ord(ch) - ord("A"))
    elif "a" <= ch <= "z":
        code = 0x8281 + (ord(ch) - ord("a"))
    elif ch == "?":
        code = 0x8148
    elif ch == " ":
        code = 0x8140
    else:
        return None
    idx = fontmod.sjis_to_glyph_index(rom, code)
    if idx is None or idx >= count:
        return None
    return fontmod.decode_glyph(data, idx, w, h)


def desenhar(tela, rows, x, largura_desenho):
    """Pinta o fundo de 16 colunas e desenha `largura_desenho` colunas.

    O fundo SUBSTITUI (nao combina). Tinta e sombra combinam entre si: onde as
    duas caem sai 3. Foi assim que o original se comportou quando medido.
    """
    for c in range(x, min(x + 16, LARGURA)):
        for l in range(ALTURA):
            tela[l][c] = COR_FUNDO

    for linha in range(12):
        for coluna in range(min(largura_desenho, 12)):
            if rows[linha][coluna] != "#":
                continue
            marcas = [(coluna + 1, linha, COR_SOMBRA),
                      (coluna, linha, COR_TINTA)]
            if linha + 1 < 12:
                marcas.insert(1, (coluna + 1, linha + 1, COR_SOMBRA))
            for cc, ll, cor in marcas:
                px, py = x + cc, ll
                if not (0 <= px < LARGURA and 0 <= py < ALTURA):
                    continue
                atual = tela[py][px]
                tela[py][px] = cor if atual == COR_FUNDO else (atual | cor)


def render(glifos, avancos, larguras_desenho):
    tela = [[0] * LARGURA for _ in range(ALTURA)]
    x = 0
    for rows, av, ld in zip(glifos, avancos, larguras_desenho):
        desenhar(tela, rows, x, ld)
        x += av
    return tela, x


def mostrar(tela, titulo, largura_util):
    simbolos = {0: " ", 1: "#", 2: "+", 3: "@", 4: "."}
    print(f"\n  {titulo}")
    for linha in tela[:13]:
        print("      " + "".join(simbolos.get(p, "?") for p in linha[:largura_util]))


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    h, _ = fontmod.read_font_header(rom)
    w, hh = h["width"], h["height"]
    data = rom[h["data_offset"]: h["data_offset"] + h["data_size"]]
    count = h["data_size"] // (fontmod.glyph_bytes_per_row(w) * hh)

    frase = "Salvar?"
    glifos = [g for g in (glifo_de(rom, data, count, w, hh, c) for c in frase) if g]

    # Como esta hoje: avanco = b+1, desenha b+1 colunas
    avancos_vwf, desenho_vwf, avancos_orig = [], [], []
    for rows in glifos:
        _, b = fontmod.ink_bounds(rows)
        av = max(1, min(12, b + 1))
        avancos_vwf.append(av)
        desenho_vwf.append(av)
        avancos_orig.append(12)

    tela_orig, larg_orig = render(glifos, avancos_orig, [12] * len(glifos))
    tela_vwf, larg_vwf = render(glifos, avancos_vwf, desenho_vwf)

    print("=" * 74)
    print(f'RENDER DE "{frase}"   (# tinta, + sombra, @ ambas, . fundo)')
    print("=" * 74)
    mostrar(tela_orig, f"ORIGINAL (12px fixo, {larg_orig}px)", larg_orig + 4)
    mostrar(tela_vwf, f"VWF ATUAL ({larg_vwf}px)", larg_vwf + 4)

    # --- o que se perdeu, por tipo de pixel ---
    print()
    print("=" * 74)
    print("O QUE SE PERDEU")
    print("=" * 74)
    conta_orig = {1: 0, 2: 0, 3: 0}
    conta_vwf = {1: 0, 2: 0, 3: 0}
    for linha in tela_orig:
        for p in linha:
            if p in conta_orig:
                conta_orig[p] += 1
    for linha in tela_vwf:
        for p in linha:
            if p in conta_vwf:
                conta_vwf[p] += 1

    nomes = {1: "tinta ", 2: "sombra", 3: "ambas "}
    for k in (1, 2, 3):
        perda = conta_orig[k] - conta_vwf[k]
        pct = 100 * perda / conta_orig[k] if conta_orig[k] else 0
        print(f"  {nomes[k]}: {conta_orig[k]:4d} -> {conta_vwf[k]:4d}   "
              f"perdeu {perda:4d} ({pct:5.1f}%)")

    print()
    if conta_orig[1] - conta_vwf[1] > 0:
        print("  Perdeu TINTA: o problema nao e so a sombra - as letras estao")
        print("  sendo cortadas de verdade.")
    else:
        print("  A tinta esta intacta. A perda e so de sombra/contorno,")
        print("  o que confirma o diagnostico.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
