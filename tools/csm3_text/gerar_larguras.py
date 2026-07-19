#!/usr/bin/env python3
"""Gera a tabela de larguras para o VWF quantizado.

A engine desenha cada glifo numa caixa de 12px e avanca sempre 0x60 bytes
(96 = 12px, a 8 bytes por coluna de pixel). O destino aceita offsets em
multiplos de 32 bytes (4px) e existem blitters para fase 0 e fase 4 - entao
avancos de 4, 8 ou 12px sao possiveis SEM tocar no blitter.

Esta tabela diz, para cada glifo, quantas unidades de 4px ele deve avancar:
    1 = 4px    2 = 8px    3 = 12px (comportamento atual)

Kanji e katakana ficam em 3 (largura cheia); latino encolhe.
"""

from __future__ import annotations

import json
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import font as fontmod

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"

# Colunas EM BRANCO entre a sombra de uma letra e a tinta da seguinte.
# 0 = colado na sombra, 1 = apertado, 2 = folgado, 3 = quase o original.
# Previa em PNG: tools/csm3_text/gerar_previa.py
FOLGA = 1

LARGURA_MAXIMA = 12  # a celula do glifo
LARGURA_ESPACO = 4   # avanco do glifo em branco


def bordas_da_tinta(rows):
    """(primeira, ultima) coluna com tinta; (None, None) se o glifo e vazio."""
    a = b = None
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
    header, _ = fontmod.read_font_header(rom)
    w, h = header["width"], header["height"]
    data = rom[header["data_offset"]: header["data_offset"] + header["data_size"]]
    count = header["data_size"] // (fontmod.glyph_bytes_per_row(w) * h)

    print("=" * 72)
    print("TABELA DE MEDIDAS PARA O VWF")
    print("=" * 72)
    print(f"  glifos: {count:,}  |  avanco em PIXELS  |  folga: {FOLGA}px")

    avancos = bytearray(count)
    recuos = bytearray(count)
    tintas = bytearray(count)
    dist = Counter()

    # Os glifos acentuados nao existem na baserom: patch_acentos.py compoe cada
    # um (letra base + acento) e grava por cima de slots livres. Medir o slot
    # como ele esta na baserom daria o recuo de OUTRO simbolo, e o desenhador
    # comecaria a pintar na coluna errada, cortando o acento. Aqui os bitmaps
    # sao recompostos do mesmo jeito, para medir o que o jogo realmente desenha.
    compostos = {}
    slots = OUT / "acentos_slots.json"
    if slots.exists():
        import patch_acentos
        from acentos import NECESSARIAS

        info = json.loads(slots.read_text(encoding="utf-8"))
        inicio = info["inicio"]
        for k, (ch, base_letra, acento) in enumerate(NECESSARIAS):
            rows = patch_acentos.compor(rom, data, w, h, count,
                                        base_letra, acento)
            if rows is not None:
                compostos[inicio + k] = (ch, rows)
        print(f"  acentuadas    : {len(compostos)} glifos medidos do bitmap "
              f"composto (slots {inicio}..{inicio + len(compostos) - 1})")
    else:
        print("  acentuadas    : sem acentos_slots.json - rode patch_acentos.py")

    for i in range(count):
        if i in compostos:
            rows = compostos[i][1]
        else:
            rows = fontmod.decode_glyph(data, i, w, h)
        a, b = bordas_da_tinta(rows)
        if a is None:
            # Glifo em branco (espaco).
            recuo, tinta, u = 0, 0, LARGURA_ESPACO
        else:
            # O desenhador agora encosta a primeira coluna de tinta em x, entao
            # o que importa e a LARGURA DA TINTA, nao onde ela termina dentro
            # da celula. O vazio a esquerda (o recuo) e descontado no desenho.
            #
            # avanco = tinta + 1 sombra + FOLGA. O +1 da sombra nao e enfeite:
            # cada pixel de tinta projeta sombra um pixel a direita, e como a
            # pintura de fundo do glifo seguinte comeca no avanco, um avanco
            # menor comeria essa sombra (medido: 30% dela sumia).
            recuo = a
            tinta = b - a + 1
            u = min(LARGURA_MAXIMA, tinta + 1 + FOLGA)
        avancos[i] = u
        recuos[i] = recuo
        tintas[i] = tinta
        dist[u] += 1
    tabela = avancos

    print()
    print("  distribuicao (avanco em pixels):")
    for u in sorted(dist):
        barra = "#" * min(46, dist[u] * 46 // max(dist.values()))
        print(f"      {u:2d}px: {dist[u]:5,d} glifos  {barra}")

    media = sum(u * n for u, n in dist.items()) / count
    print(f"\n  avanco medio (fonte inteira): {media:.2f}px  (era 12px fixo)")

    # O que importa e o latino, que e o que a traducao usa.
    faixas = [("digitos", 0x824F, 0x8258), ("A-Z", 0x8260, 0x8279),
              ("a-z", 0x8281, 0x829A)]
    total_u = total_n = 0
    print()
    print("  so os glifos latinos:")
    for nome, lo, hi in faixas:
        us = []
        for code in range(lo, hi + 1):
            idx = fontmod.sjis_to_glyph_index(rom, code)
            if idx is not None and idx < count:
                us.append(tabela[idx])
        if us:
            print(f"      {nome:8s}: media {sum(us)/len(us):.2f}px")
            total_u += sum(us)
            total_n += len(us)
    if total_n:
        media_lat = total_u / total_n
        print(f"      TOTAL   : media {media_lat:.2f}px  "
              f"(economia de {100*(1-media_lat/12):.1f}% contra os 12px fixos)")

    # A tabela e indexada por (endereco_do_glifo - base_da_fonte) >> 3.
    # Como cada glifo ocupa 24 bytes, esse indice vale glifo*3 - entao sobram
    # 3 entradas por glifo. Antes duas ficavam zeradas; agora as tres sao usadas
    # e o custo de memoria e o mesmo. Evita dividir por 24 em thumb, que exigiria
    # multiplicacao magica.
    #     [i*3 + 0] avanco   [i*3 + 1] recuo   [i*3 + 2] largura da tinta
    expandida = bytearray(count * 3)
    for i in range(count):
        expandida[i * 3] = avancos[i]
        expandida[i * 3 + 1] = recuos[i]
        expandida[i * 3 + 2] = tintas[i]

    linhas = [
        "\t.include \"asm/macros.inc\"",
        "\t.include \"constants/constants.inc\"",
        "",
        "\t.section .rodata",
        "",
        "@ Medidas dos glifos para o VWF.",
        "@ Gerado por tools/csm3_text/gerar_larguras.py - nao editar a mao.",
        "@",
        "@ INDEXACAO: i = (endereco_do_glifo - *gUnk_03002984) >> 3",
        "@ Cada glifo ocupa 24 bytes, entao i vale glifo*3 e sobram 3 entradas:",
        "@     [i+0] avanco ate o proximo glifo, em pixels",
        "@     [i+1] recuo: colunas vazias a esquerda dentro da celula de 12px",
        "@     [i+2] largura da tinta, em colunas",
        "@ Descontar o recuo e o que deixa o espacamento constante.",
        "",
        "\t.align 2, 0",
        "gPtBrLarguras::",
    ]
    for i in range(0, len(expandida), 24):
        bloco = expandida[i:i + 24]
        linhas.append("\t.byte " + ", ".join(str(b) for b in bloco))
    linhas.append("")

    destino = REPO / "data" / "ptbr_larguras.s"
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"\n  gerado: data/ptbr_larguras.s "
          f"({len(expandida):,} bytes, indexada por endereco)")

    (OUT / "larguras.bin").write_bytes(bytes(tabela))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
