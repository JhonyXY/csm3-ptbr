#!/usr/bin/env python3
"""Despeja uma regiao da ROM decodificando as strings Shift-JIS u16.

Uso:
    python3 dump_region.py 0xBB100 0x200
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
from script_text import is_sjis_pair, word_to_sjis

REPO = Path(__file__).resolve().parents[2]


def decode_run(rom: bytes, pos: int, limite: int = 80) -> tuple[str, int]:
    """Le palavras u16 SJIS a partir de pos ate encontrar 0x0000."""
    raw = bytearray()
    n = 0
    while pos + 2 <= len(rom) and n < limite:
        w = struct.unpack_from("<H", rom, pos)[0]
        if w == 0:
            pos += 2
            break
        if not is_sjis_pair(w):
            break
        raw += word_to_sjis(w)
        pos += 2
        n += 1
    try:
        return bytes(raw).decode("shift_jis"), pos
    except UnicodeDecodeError:
        return "", pos


def main() -> int:
    inicio = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0xBB100
    tamanho = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x200

    rom = csm3rom.load_rom(REPO / "baserom.gba")

    print("=" * 72)
    print(f"REGIAO 0x{inicio:07X}..0x{inicio+tamanho:07X}  "
          f"(GBA 0x{0x08000000+inicio:08X})")
    print("=" * 72)

    # Strings encontradas
    print("\n  --- strings SJIS terminadas em 0x0000 ---")
    pos = inicio
    while pos < inicio + tamanho:
        w = struct.unpack_from("<H", rom, pos)[0]
        if is_sjis_pair(w):
            texto, fim = decode_run(rom, pos)
            if texto:
                print(f"      0x{pos:07X}  (GBA 0x{0x08000000+pos:08X})  "
                      f"{len(texto):2d} chars  \"{texto}\"")
                pos = fim
                continue
        pos += 2

    # Hexdump para ver a estrutura em volta
    print("\n  --- hexdump ---")
    for row in range(0, min(tamanho, 0x100), 16):
        off = inicio + row
        words = struct.unpack_from("<8H", rom, off)
        hexs = " ".join(f"{w:04X}" for w in words)
        chars = ""
        for w in words:
            if is_sjis_pair(w):
                try:
                    chars += word_to_sjis(w).decode("shift_jis")
                except UnicodeDecodeError:
                    chars += "."
            elif w == 0:
                chars += "·"
            else:
                chars += "?"
        print(f"      0x{off:07X}: {hexs}  {chars}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
