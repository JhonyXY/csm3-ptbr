#!/usr/bin/env python3
"""Por que umas letras ficam coladas e outras afastadas? Mede o bearing.

Voce disse: "eles ficaram coladinhos i m mas outras letras nao". Isso nao e
espacamento grande demais nem pequeno demais - e espacamento IRREGULAR, que tem
uma causa unica e mensuravel.

O avanco hoje sai do limite DIREITO da tinta (coluna b). Mas cada glifo tambem
tem um vazio a ESQUERDA (coluna a), e esse vazio nao e removido. Entao o espaco
que aparece entre duas letras e:

    folga_depois(esquerda) + bearing_esquerdo(direita)

Como o bearing esquerdo varia de glifo para glifo, o espaco varia junto. Um 'i'
com bearing 4 abre um buraco; um 'm' com bearing 0 cola na letra anterior.

Este script mede a e b de cada glifo e mostra o espaco resultante par a par.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import font as fontmod

REPO = Path(__file__).resolve().parents[2]

SJIS = {}
for _i in range(26):
    SJIS[chr(ord("A") + _i)] = 0x8260 + _i
    SJIS[chr(ord("a") + _i)] = 0x8281 + _i
for _i in range(10):
    SJIS[chr(ord("0") + _i)] = 0x824F + _i
SJIS["?"] = 0x8148
SJIS[" "] = 0x8140


def bounds(rows):
    """(primeira, ultima) coluna com tinta. (None, None) se vazio."""
    a, b = None, None
    for r in rows:
        for c, px in enumerate(r):
            if px == "#":
                if a is None or c < a:
                    a = c
                if b is None or c > b:
                    b = c
    return a, b


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    h, _ = fontmod.read_font_header(rom)
    w, hh = h["width"], h["height"]
    dados = rom[h["data_offset"]: h["data_offset"] + h["data_size"]]
    count = h["data_size"] // (fontmod.glyph_bytes_per_row(w) * hh)

    def glifo(ch):
        code = SJIS.get(ch)
        if code is None:
            return None
        idx = fontmod.sjis_to_glyph_index(rom, code)
        if idx is None or idx >= count:
            return None
        return fontmod.decode_glyph(dados, idx, w, hh)

    print("=" * 78)
    print("BEARING DE CADA GLIFO  (a = vazio a esquerda, b = ultima col de tinta)")
    print("=" * 78)
    print("  ch    a   b  tinta  avanco_hoje")
    print("  " + "-" * 40)

    letras = "SimalvrABCDEFGHIJKLMNOPQRSTUVWXYZ?"
    dados_ch = {}
    for ch in letras:
        rows = glifo(ch)
        if rows is None:
            continue
        a, b = bounds(rows)
        if a is None:
            continue
        # avanco de hoje: tabela = b+2, mais ESPACO_ENTRE_LETRAS=1 no C
        avanco = min(12, min(12, max(1, b + 2)) + 1)
        dados_ch[ch] = (a, b, avanco)
        print(f"  {ch:3s} {a:3d} {b:3d} {b - a + 1:6d} {avanco:12d}")

    print()
    print("=" * 78)
    print("ESPACO VISIVEL ENTRE PARES (colunas em branco entre sombra e tinta)")
    print("=" * 78)
    print("  espaco = avanco(esq) - b(esq) - 1(sombra) + a(dir)")
    print()

    pares = [("S", "i"), ("i", "m"), ("S", "a"), ("a", "l"), ("l", "v"),
             ("v", "a"), ("a", "r"), ("r", "?"), ("m", "a"), ("A", "i")]
    espacos = []
    for e, d in pares:
        if e not in dados_ch or d not in dados_ch:
            continue
        ae, be, av = dados_ch[e]
        ad, bd, _ = dados_ch[d]
        espaco = av - be - 1 + ad
        espacos.append(espaco)
        print(f"  {e}{d} : avanco {av:2d}  b_esq {be:2d}  bearing_dir {ad:2d}"
              f"   -> {espaco:2d} px em branco")

    if espacos:
        print()
        print(f"  menor: {min(espacos)}px   maior: {max(espacos)}px"
              f"   variacao: {max(espacos) - min(espacos)}px")
        print()
        if max(espacos) - min(espacos) >= 2:
            print("  CONFIRMADO: o espaco NAO e constante. A causa e o bearing")
            print("  esquerdo, que muda de glifo para glifo e nao esta sendo")
            print("  descontado. Nao adianta mexer no avanco - tem que desenhar")
            print("  o glifo deslocado -a colunas.")
        else:
            print("  O espaco ja e praticamente constante - a causa e outra.")

    print()
    print("=" * 78)
    print("COM O BEARING DESCONTADO")
    print("=" * 78)
    print("  desenhar em (x - a) e avancar (b - a + 1) + 1 sombra + 1 folga")
    print()
    novos = []
    for e, d in pares:
        if e not in dados_ch or d not in dados_ch:
            continue
        ae, be, _ = dados_ch[e]
        av = (be - ae + 1) + 2
        espaco = av - (be - ae) - 1
        novos.append(espaco)
        print(f"  {e}{d} : avanco {av:2d}   -> {espaco:2d} px em branco")
    if novos:
        print()
        print(f"  menor: {min(novos)}px   maior: {max(novos)}px"
              f"   variacao: {max(novos) - min(novos)}px")

    # largura da frase inteira, dos dois jeitos
    for frase in ("Salvar?", "Sim"):
        hoje = sum(dados_ch[c][2] for c in frase if c in dados_ch)
        novo = sum((dados_ch[c][1] - dados_ch[c][0] + 1) + 2
                   for c in frase if c in dados_ch)
        print(f'\n  "{frase}": original {12 * len(frase)}px | '
              f"hoje {hoje}px | com bearing {novo}px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
