#!/usr/bin/env python3
"""Renderiza o texto da ROM usando a fonte e a tabela de lookup do proprio jogo.

Reproduz o caminho real de desenho: SJIS -> sub_0800348C (tabela de lookup) ->
indice de glifo -> bitmap 1bpp 12x12. O que aparecer aqui e o que o jogador ve.

Uso:
    python3 render_screen.py                    # ROM traduzida
    python3 render_screen.py --rom baserom.gba  # original, para comparar
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import font as fontmod
import walker
from script_text import word_to_sjis

REPO = Path(__file__).resolve().parents[2]


def render_line(rom: bytes, data: bytes, count: int, w: int, h: int,
                words: list[int], vwf: bool = False) -> list[str]:
    """Devolve as linhas de pixels de uma string."""
    glyphs = []
    for word in words:
        pair = word_to_sjis(word)
        sjis_be = (pair[0] << 8) | pair[1]
        idx = fontmod.sjis_to_glyph_index(rom, sjis_be)
        if idx is None or idx >= count:
            glyphs.append(None)
            continue
        glyphs.append(fontmod.decode_glyph(data, idx, w, h))

    rows = []
    for y in range(h):
        line = []
        for g in glyphs:
            if g is None:
                line.append("?" * w)
                continue
            if not vwf:
                line.append(g[y])
                continue
            if not any("#" in r for r in g):
                line.append("..")  # espaco estreito
                continue
            a, b = fontmod.ink_bounds(g)
            line.append(g[y][a : b + 1] + ".")
        rows.append("".join(line))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default="csm3_ptbr.gba")
    ap.add_argument("--script", type=int, default=8)
    ap.add_argument("--limite", type=int, default=6)
    ap.add_argument("--vwf", action="store_true",
                    help="simula o VWF (recorte na tinta + 1px)")
    args = ap.parse_args()

    rom_path = REPO / args.rom
    rom = csm3rom.load_rom(rom_path)

    header, _ = fontmod.read_font_header(rom)
    w, h = header["width"], header["height"]
    data = rom[header["data_offset"] : header["data_offset"] + header["data_size"]]
    count = header["data_size"] // (fontmod.glyph_bytes_per_row(w) * h)

    auto_map = walker.load_auto_map()
    archive = csm3rom.open_archive(rom, csm3rom.SCRIPT_ARCHIVE)
    script = csm3rom.load_script(archive, args.script)
    if script is None:
        print(f"script {args.script} vazio", file=sys.stderr)
        return 1

    result = walker.walk(bytes(script.body), auto_map)
    textos = result.text_instructions

    modo = "VWF simulado" if args.vwf else f"avanco fixo {w}px"
    print("=" * 72)
    print(f"RENDER DE {rom_path.name} - script {args.script} - {modo}")
    print("=" * 72)

    for ins in textos[: args.limite]:
        words = ins.text_words or []
        if not words:
            continue
        pair_bytes = bytearray()
        for word in words:
            pair_bytes += word_to_sjis(word)
        try:
            texto = bytes(pair_bytes).decode("shift_jis")
        except UnicodeDecodeError:
            texto = "(nao decodifica)"

        largura = len(words) * w if not args.vwf else None
        px = f"{largura}px" if largura else ""
        print(f"\n  @0x{ins.offset:04X}  \"{texto}\"  {px}")
        for row in render_line(rom, data, count, w, h, words, vwf=args.vwf):
            print(f"      {row}")

    print()
    print(f"  strings no script: {len(textos)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
