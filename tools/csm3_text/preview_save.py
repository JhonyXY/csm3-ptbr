#!/usr/bin/env python3
"""Renderiza a caixa de dialogo do save como ela vai aparecer na tela.

Le as strings pelos ponteiros da ROM traduzida e desenha com os glifos reais,
no mesmo avanco fixo de 12px que a engine usa hoje.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import font as fontmod
from script_text import is_sjis_pair, word_to_sjis

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"

CAIXA_PX = 192  # largura util aproximada da caixa de dialogo


def ler_por_ponteiro(rom: bytes, ptr_off: int) -> list[int]:
    ptr = struct.unpack_from("<I", rom, ptr_off)[0]
    pos = ptr - 0x08000000
    palavras = []
    while pos + 2 <= len(rom):
        w = struct.unpack_from("<H", rom, pos)[0]
        if w == 0 or not is_sjis_pair(w):
            break
        palavras.append(w)
        pos += 2
    return palavras


def desenhar(rom, data, count, w, h, palavras, vwf=False) -> list[str]:
    glyphs = []
    for word in palavras:
        pair = word_to_sjis(word)
        idx = fontmod.sjis_to_glyph_index(rom, (pair[0] << 8) | pair[1])
        glyphs.append(
            fontmod.decode_glyph(data, idx, w, h)
            if idx is not None and idx < count else None
        )
    linhas = []
    for y in range(h):
        out = []
        for g in glyphs:
            if g is None:
                out.append("?" * w)
            elif not vwf:
                out.append(g[y])
            elif not any("#" in r for r in g):
                out.append("..")
            else:
                a, b = fontmod.ink_bounds(g)
                out.append(g[y][a:b + 1] + ".")
        linhas.append("".join(out))
    return linhas


def caixa(titulo: str, linhas_de_texto: list[list[str]], largura: int) -> None:
    print(f"  +{'-' * largura}+   {titulo}")
    for bloco in linhas_de_texto:
        for linha in bloco:
            corte = linha[:largura].ljust(largura)
            vazou = "  <== VAZOU" if len(linha) > largura else ""
            print(f"  |{corte}|{vazou}")
        print(f"  |{' ' * largura}|")
    print(f"  +{'-' * largura}+")


def main() -> int:
    rom = csm3rom.load_rom(REPO / "csm3_ptbr.gba")
    header, _ = fontmod.read_font_header(rom)
    w, h = header["width"], header["height"]
    data = rom[header["data_offset"]: header["data_offset"] + header["data_size"]]
    count = header["data_size"] // (fontmod.glyph_bytes_per_row(w) * h)

    dados = json.loads((OUT / "sysstrings.json").read_text(encoding="utf-8"))
    por_jp = {e["jp"]: e for e in dados["strings"]}

    cena = ["セーブしますか？", "は　い", "いいえ"]

    for vwf in (False, True):
        modo = "COM VWF (ainda nao implementado)" if vwf else "COMO ESTA HOJE (12px fixos)"
        print("=" * 72)
        print(f"CAIXA DE SAVE - {modo}")
        print("=" * 72)
        blocos = []
        for jp in cena:
            e = por_jp[jp]
            palavras = ler_por_ponteiro(rom, e["ponteiro"])
            blocos.append(desenhar(rom, data, count, w, h, palavras, vwf=vwf))
        caixa(f"caixa de {CAIXA_PX}px", blocos, CAIXA_PX)
        print()

    print("=" * 72)
    print("LARGURA DE CADA LINHA")
    print("=" * 72)
    for jp in cena:
        e = por_jp[jp]
        palavras = ler_por_ponteiro(rom, e["ponteiro"])
        fixo = len(palavras) * w
        linhas_vwf = desenhar(rom, data, count, w, h, palavras, vwf=True)
        largura_vwf = max(len(l.rstrip(".")) for l in linhas_vwf) if linhas_vwf else 0
        print(f"  \"{e['pt']:<16}\"  fixo {fixo:3d}px | vwf ~{largura_vwf:3d}px  "
              f"(era \"{jp}\")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
