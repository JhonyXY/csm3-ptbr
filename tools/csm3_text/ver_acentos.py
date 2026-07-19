#!/usr/bin/env python3
"""Renderiza as acentuadas direto da ROM construida, pelo caminho do jogo.

Usa a tabela de lookup real (sub_0800348C) para converter o codigo Shift-JIS em
indice de glifo e desenha o bitmap. O que aparecer aqui e o que o jogador ve.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import encoder
import font as fontmod
from script_text import word_to_sjis

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"


def main() -> int:
    rom_path = REPO / "csm3.gba"
    rom = csm3rom.load_rom(rom_path)
    header, _ = fontmod.read_font_header(rom)
    w, h = header["width"], header["height"]
    data = rom[header["data_offset"]: header["data_offset"] + header["data_size"]]
    count = header["data_size"] // (fontmod.glyph_bytes_per_row(w) * h)

    mapa = json.loads((OUT / "acentos_mapa.json").read_text(encoding="utf-8"))

    print("=" * 72)
    print(f"ACENTUADAS NA ROM CONSTRUIDA ({rom_path.name})")
    print("=" * 72)

    faltando = []
    for ch, code_hex in mapa.items():
        code = int(code_hex, 16)
        idx = fontmod.sjis_to_glyph_index(rom, code)
        if idx is None or idx >= count:
            faltando.append(ch)
    print(f"  glifos mapeados : {len(mapa) - len(faltando)}/{len(mapa)}")
    if faltando:
        print(f"  sem glifo       : {', '.join(faltando)}")

    print()
    print("  --- amostra desenhada ---")
    for ch in ("á", "ã", "é", "ç", "õ", "Á"):
        code = int(mapa[ch], 16)
        idx = fontmod.sjis_to_glyph_index(rom, code)
        print(f"\n  '{ch}' (SJIS 0x{code:04X} -> glifo {idx})")
        if idx is None or idx >= count:
            print("      SEM GLIFO")
            continue
        for r in fontmod.decode_glyph(data, idx, w, h):
            print(f"      {r}")

    # --- palavras inteiras, como vao aparecer ---
    print()
    print("=" * 72)
    print("PALAVRAS RENDERIZADAS")
    print("=" * 72)
    for palavra in ("Não", "Ação", "Água", "coração"):
        palavras = encoder.encode(palavra)
        glifos = []
        for wd in palavras:
            par = word_to_sjis(wd)
            idx = fontmod.sjis_to_glyph_index(rom, (par[0] << 8) | par[1])
            glifos.append(fontmod.decode_glyph(data, idx, w, h)
                          if idx is not None and idx < count else None)
        print(f"\n  \"{palavra}\"")
        for y in range(h):
            linha = "".join(g[y] if g else "?" * w for g in glifos)
            print(f"      {linha}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
