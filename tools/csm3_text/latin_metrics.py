#!/usr/bin/env python3
"""Mede a largura util APENAS dos glifos latinos.

A media geral da fonte (10,5px) e dominada pelos kanji, que legitimamente
ocupam a caixa inteira. Como a traducao troca kanji por letras latinas, o numero
que importa para dimensionar o VWF e a largura das letras.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import font as fontmod

ROM_PATH = Path(__file__).resolve().parents[2] / "baserom.gba"

# Faixas Shift-JIS de largura total (zenkaku) que ja existem na fonte.
RANGES = [
    ("digitos 0-9", 0x824F, 0x8258),
    ("maiusculas A-Z", 0x8260, 0x8279),
    ("minusculas a-z", 0x8281, 0x829A),
]

# Pontuacao avulsa, com o caractere ASCII correspondente.
PUNCT = {
    0x8140: " ", 0x8141: ",", 0x8142: ".", 0x8143: ",", 0x8144: ".",
    0x8145: ".", 0x8146: ":", 0x8147: ";", 0x8148: "?", 0x8149: "!",
    0x815B: "-", 0x8169: "(", 0x816A: ")",
}


def main() -> int:
    rom = csm3rom.load_rom(ROM_PATH)
    header, _ = fontmod.read_font_header(rom)
    w, h = header["width"], header["height"]
    data = rom[header["data_offset"] : header["data_offset"] + header["data_size"]]
    count = header["data_size"] // (fontmod.glyph_bytes_per_row(w) * h)

    print("=" * 72)
    print("LARGURA UTIL DOS GLIFOS LATINOS (os que a traducao vai usar)")
    print("=" * 72)

    all_widths = []
    for label, lo, hi in RANGES:
        widths = []
        missing = []
        for code in range(lo, hi + 1):
            idx = fontmod.sjis_to_glyph_index(rom, code)
            if idx is None or idx >= count:
                missing.append(code)
                continue
            rows = fontmod.decode_glyph(data, idx, w, h)
            if not any("#" in r for r in rows):
                missing.append(code)
                continue
            a, b = fontmod.ink_bounds(rows)
            widths.append(b - a + 1)

        if widths:
            avg = sum(widths) / len(widths)
            all_widths.extend(widths)
            print(
                f"  {label:16s}: {len(widths):2d} glifos | "
                f"min {min(widths):2d}px  media {avg:5.2f}px  max {max(widths):2d}px"
            )
        if missing:
            print(f"      ausentes: {len(missing)}")

    punct_widths = []
    for code, ch in PUNCT.items():
        idx = fontmod.sjis_to_glyph_index(rom, code)
        if idx is None or idx >= count:
            continue
        rows = fontmod.decode_glyph(data, idx, w, h)
        if not any("#" in r for r in rows):
            punct_widths.append(3)  # espaco: largura arbitraria
            continue
        a, b = fontmod.ink_bounds(rows)
        punct_widths.append(b - a + 1)
    if punct_widths:
        print(
            f"  {'pontuacao':16s}: {len(punct_widths):2d} glifos | "
            f"media {sum(punct_widths)/len(punct_widths):5.2f}px"
        )

    print()
    if all_widths:
        avg = sum(all_widths) / len(all_widths)
        # +1px de espacamento entre letras, que o VWF precisa acrescentar.
        avg_spaced = avg + 1
        print(f"  media das letras          : {avg:.2f}px")
        print(f"  com 1px de espacamento    : {avg_spaced:.2f}px")
        print(f"  avanco fixo atual         : {w}px")
        print(f"  ECONOMIA REAL DO VWF      : {100 * (1 - avg_spaced / w):.1f}%")
        print()

        # Quantos caracteres cabem por linha? A caixa de dialogo tem 240px de
        # largura (tela da GBA), na pratica ~224px uteis.
        for box in (224, 240):
            fixed = box // w
            vwf = int(box / avg_spaced)
            print(
                f"  caixa de {box}px: {fixed} chars com avanco fixo -> "
                f"{vwf} chars com VWF  ({vwf/fixed:.2f}x)"
            )

    print()
    print("=" * 72)
    print("AMOSTRA RENDERIZADA - frase em portugues com os glifos existentes")
    print("=" * 72)
    frase = "Ola mundo"
    glyphs = []
    for ch in frase:
        if ch == " ":
            code = 0x8140
        elif ch.isupper():
            code = 0x8260 + (ord(ch) - ord("A"))
        elif ch.islower():
            code = 0x8281 + (ord(ch) - ord("a"))
        else:
            continue
        idx = fontmod.sjis_to_glyph_index(rom, code)
        if idx is None or idx >= count:
            continue
        glyphs.append(fontmod.decode_glyph(data, idx, w, h))

    print(f"  '{frase}' com avanco fixo de {w}px:")
    for y in range(h):
        print("      " + "".join(g[y] for g in glyphs))

    print()
    print(f"  '{frase}' com VWF (recorte na tinta + 1px):")
    for y in range(h):
        line = []
        for g in glyphs:
            a, b = fontmod.ink_bounds(g)
            if not any("#" in r for r in g):
                line.append("..." )  # espaco
            else:
                line.append(g[y][a : b + 1] + ".")
        print("      " + "".join(line))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
