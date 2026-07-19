#!/usr/bin/env python3
"""Mapeia a tabela de strings de sistema (menus de save/item/loja).

Diferente do texto de dialogo, estas strings ficam fora dos archives, cruas na
ROM, e sao referenciadas por uma TABELA DE PONTEIROS - o que significa que a
traducao nao precisa caber no espaco original: basta escrever no espaco livre e
reapontar.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
from script_text import is_sjis_pair, word_to_sjis

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"

# Ponteiro conhecido para "セーブしますか？"; a tabela e varrida a partir dele.
ANCORA = 0x0BC9F20


def ler_string(rom: bytes, pos: int, limite: int = 120) -> str | None:
    raw = bytearray()
    n = 0
    while pos + 2 <= len(rom) and n < limite:
        w = struct.unpack_from("<H", rom, pos)[0]
        if w == 0:
            break
        if not is_sjis_pair(w):
            return None
        raw += word_to_sjis(w)
        pos += 2
        n += 1
    try:
        return bytes(raw).decode("shift_jis")
    except UnicodeDecodeError:
        return None


def eh_entrada_valida(rom: bytes, off: int) -> tuple[bool, str | None]:
    val = struct.unpack_from("<I", rom, off)[0]
    if not (0x08000000 <= val < 0x0A000000):
        return False, None
    destino = val - 0x08000000
    if destino >= len(rom):
        return False, None
    s = ler_string(rom, destino)
    if s is None or not s:
        return False, None
    return True, s


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")

    # Varre para tras e para frente a partir da ancora.
    inicio = ANCORA
    while inicio - 4 >= 0:
        ok, _ = eh_entrada_valida(rom, inicio - 4)
        if not ok:
            break
        inicio -= 4

    fim = ANCORA
    while fim + 4 < len(rom):
        ok, _ = eh_entrada_valida(rom, fim + 4)
        if not ok:
            break
        fim += 4

    count = (fim - inicio) // 4 + 1
    print("=" * 72)
    print("TABELA DE STRINGS DE SISTEMA")
    print("=" * 72)
    print(f"  tabela : 0x{inicio:07X}..0x{fim+3:07X}  (GBA 0x{0x08000000+inicio:08X})")
    print(f"  entradas: {count}")
    print()

    entradas = []
    for i in range(count):
        off = inicio + i * 4
        val = struct.unpack_from("<I", rom, off)[0]
        destino = val - 0x08000000
        s = ler_string(rom, destino)
        entradas.append({
            "indice": i,
            "ponteiro": off,
            "alvo": destino,
            "jp": s,
            "chars": len(s) if s else 0,
            "bytes": (len(s) * 2 + 2) if s else 0,
        })
        print(f"  [{i:3d}] ptr 0x{off:07X} -> 0x{destino:07X}  "
              f"{len(s):2d}ch  \"{s}\"")

    # Strings compartilhadas por mais de um ponteiro: traduzir uma afeta as duas.
    alvos = {}
    for e in entradas:
        alvos.setdefault(e["alvo"], []).append(e["indice"])
    compartilhadas = {k: v for k, v in alvos.items() if len(v) > 1}
    print()
    print(f"  strings distintas   : {len(alvos)}")
    print(f"  alvos compartilhados: {len(compartilhadas)}")
    for alvo, idxs in list(compartilhadas.items())[:6]:
        print(f"      0x{alvo:07X} usado pelos indices {idxs}")

    out = OUT / "sysstrings.json"
    out.write_text(
        json.dumps({
            "_meta": {
                "tabela": f"0x{inicio:07X}",
                "entradas": count,
                "nota": "strings cruas na ROM, referenciadas por ponteiro - "
                        "a traducao nao precisa caber no espaco original",
            },
            "strings": [dict(e, pt="") for e in entradas],
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n  gravado: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
