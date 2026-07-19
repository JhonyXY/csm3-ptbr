#!/usr/bin/env python3
"""Extrai e inspeciona a fonte do jogo.

A fonte fica no archive 3, entrada 2, LIDA DIRETO DA ROM (nao e comprimida).
O cabecalho de 0x1C bytes se autodescreve com magic "BIT\\0".

Cada glifo e 1bpp: 12 linhas de 2 bytes. Por linha, o byte 0 traz os pixels 0-7
(MSB primeiro) e o nibble alto do byte 1 traz os pixels 8-11. O nibble baixo do
byte 1 nao e usado.
"""

from __future__ import annotations

import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import script_text

ROM_PATH = Path(__file__).resolve().parents[2] / "baserom.gba"
OUT_DIR = Path(__file__).parent / "_out"

FONT_ENTRY = 2
BIT_MAGIC = b"BIT\0"

# Tabelas de lookup Shift-JIS -> indice de glifo (offsets no arquivo da ROM).
LOOKUP_LOW = (0x0B6D624, 0x81, 0x9F)   # lead bytes 0x81..0x9F
LOOKUP_HIGH = (0x0B704A4, 0xE0, 0xEB)  # lead bytes 0xE0..0xEB
TRAILS_PER_LEAD = 192  # trail bytes 0x40..0xFF


def read_font_header(rom: bytes) -> tuple[dict, int]:
    arc = csm3rom.open_archive(rom, csm3rom.FONT_ARCHIVE)
    entry = arc.entries[FONT_ENTRY]
    base = entry.offset

    magic = rom[base : base + 4]
    if magic != BIT_MAGIC:
        raise ValueError(f"magic {magic!r} em 0x{base:X}, esperado {BIT_MAGIC!r}")

    width, height = struct.unpack_from("<HH", rom, base + 0x14)
    data_size = struct.unpack_from("<I", rom, base + 0x18)[0]

    header = {
        "base": base,
        "width": width,
        "height": height,
        "data_size": data_size,
        "data_offset": base + 0x1C,
    }
    return header, base


def glyph_bytes_per_row(width: int) -> int:
    return (width + 7) // 8


def decode_glyph(data: bytes, index: int, width: int, height: int) -> list[str]:
    """Devolve o glifo como linhas de texto ('#' aceso, '.' apagado)."""
    row_bytes = glyph_bytes_per_row(width)
    size = row_bytes * height
    start = index * size
    rows = []
    for y in range(height):
        row = data[start + y * row_bytes : start + (y + 1) * row_bytes]
        bits = []
        for x in range(width):
            byte = row[x // 8]
            bit = (byte >> (7 - (x % 8))) & 1
            bits.append("#" if bit else ".")
        rows.append("".join(bits))
    return rows


def sjis_to_glyph_index(rom: bytes, sjis_be: int) -> int | None:
    """Reproduz sub_0800348C: converte um codigo Shift-JIS em indice de glifo."""
    lead = sjis_be >> 8
    trail = sjis_be & 0xFF
    if LOOKUP_LOW[1] <= lead <= LOOKUP_LOW[2]:
        table, first = LOOKUP_LOW[0], LOOKUP_LOW[1]
    elif LOOKUP_HIGH[1] <= lead <= LOOKUP_HIGH[2]:
        table, first = LOOKUP_HIGH[0], LOOKUP_HIGH[1]
    else:
        return None
    i = (lead - first) * TRAILS_PER_LEAD + (trail - 0x40)
    value = struct.unpack_from("<H", rom, table + i * 2)[0]
    return value - 1 if value else None


def ink_bounds(rows: list[str]) -> tuple[int, int]:
    """Primeira e ultima coluna com pixel aceso - a base do VWF."""
    first, last = None, None
    for row in rows:
        for x, ch in enumerate(row):
            if ch == "#":
                if first is None or x < first:
                    first = x
                if last is None or x > last:
                    last = x
    if first is None:
        return (0, 0)
    return (first, last)


def main() -> int:
    rom = csm3rom.load_rom(ROM_PATH)
    OUT_DIR.mkdir(exist_ok=True)

    header, base = read_font_header(rom)
    w, h = header["width"], header["height"]
    row_bytes = glyph_bytes_per_row(w)
    glyph_size = row_bytes * h
    count = header["data_size"] // glyph_size

    print("=" * 72)
    print("FONTE")
    print("=" * 72)
    print(f"  archive 3, entrada {FONT_ENTRY} @ 0x{base:07X}")
    print(f"  dimensoes    : {w} x {h} px, 1bpp")
    print(f"  bytes/glifo  : {glyph_size} ({row_bytes} por linha x {h} linhas)")
    print(f"  tamanho dados: {header['data_size']:,} bytes")
    print(f"  glifos       : {count:,}")

    data = rom[header["data_offset"] : header["data_offset"] + header["data_size"]]

    # Renderiza alguns caracteres conhecidos para provar que o decoder esta certo.
    print()
    print("=" * 72)
    print("PROVA DO DECODER - caracteres conhecidos renderizados")
    print("=" * 72)
    probes = [
        (0x824F, "0"), (0x8250, "1"), (0x8260, "A"), (0x8281, "a"),
        (0x93FA, "日"), (0x967B, "本"), (0x83C1, "gamma (placeholder)"),
    ]
    for sjis_be, label in probes:
        idx = sjis_to_glyph_index(rom, sjis_be)
        if idx is None or idx >= count:
            print(f"\n  SJIS 0x{sjis_be:04X} ({label}): sem glifo")
            continue
        rows = decode_glyph(data, idx, w, h)
        lo, hi = ink_bounds(rows)
        print(f"\n  SJIS 0x{sjis_be:04X} ({label}) -> glifo {idx}, tinta em x={lo}..{hi} "
              f"(largura util {hi - lo + 1})")
        for row in rows:
            print(f"      {row}")

    # Levantamento de largura util: e o que o VWF vai economizar.
    print()
    print("=" * 72)
    print("LARGURA UTIL DOS GLIFOS (potencial do VWF)")
    print("=" * 72)
    widths = Counter()
    blank = 0
    for i in range(count):
        rows = decode_glyph(data, i, w, h)
        lo, hi = ink_bounds(rows)
        if not any("#" in r for r in rows):
            blank += 1
            continue
        widths[hi - lo + 1] += 1

    print(f"  glifos em branco: {blank:,}")
    print("  distribuicao da largura util:")
    for width in sorted(widths):
        n = widths[width]
        bar = "#" * min(50, n * 50 // max(widths.values()))
        print(f"      {width:2d}px : {n:5,d}  {bar}")
    if widths:
        total = sum(width * n for width, n in widths.items())
        avg = total / sum(widths.values())
        print(f"\n  largura util media: {avg:.2f}px  (avanco fixo atual: {w}px)")
        print(f"  economia potencial do VWF: {100 * (1 - avg / w):.1f}%")

    # Quais glifos o jogo realmente usa? O resto e espaco livre para latino.
    print()
    print("=" * 72)
    print("OCUPACAO REAL DA FONTE")
    print("=" * 72)
    used = set()
    for script in csm3rom.iter_scripts(rom):
        for run in script_text.scan_text_runs(bytes(script.body), script.index):
            for word in run.words:
                pair = script_text.word_to_sjis(word)
                sjis_be = (pair[0] << 8) | pair[1]
                idx = sjis_to_glyph_index(rom, sjis_be)
                if idx is not None and 0 <= idx < count:
                    used.add(idx)

    print(f"  glifos usados nos dialogos: {len(used):,} de {count:,}")
    print(f"  glifos livres              : {count - len(used):,}")
    print(f"  ocupacao                   : {100 * len(used) / count:.1f}%")
    print()
    print(f"  Um alfabeto latino completo (maiusculas, minusculas, acentuadas,")
    print(f"  pontuacao) cabe em ~150 glifos. Espaco livre: {count - len(used):,}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
