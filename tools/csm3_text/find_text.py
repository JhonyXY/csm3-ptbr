#!/usr/bin/env python3
"""Procura uma string japonesa no jogo.

Busca em duas frentes:
  1. nas strings ja extraidas do archive 2 (scripts)
  2. nos bytes crus da ROM inteira, caso o texto viva fora dos scripts
     (menus de sistema costumam ficar em outro archive ou no proprio codigo)

Uso:
    python3 find_text.py "はい"
    python3 find_text.py "セーブしますか"
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import lz77

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"


def buscar_nos_scripts(alvo: str) -> list[dict]:
    path = OUT / "textos_originais.json"
    if not path.exists():
        return []
    d = json.loads(path.read_text(encoding="utf-8"))
    return [e for e in d["strings"] if alvo in e["jp"]]


def buscar_na_rom_crua(rom: bytes, alvo: str) -> list[int]:
    raw = alvo.encode("shift_jis")
    hits = []
    pos = rom.find(raw)
    while pos != -1:
        hits.append(pos)
        pos = rom.find(raw, pos + 1)
    return hits


def buscar_nos_archives(rom: bytes, alvo: str) -> list[tuple[int, int, int]]:
    """Procura dentro dos blobs descomprimidos de TODOS os archives."""
    raw = alvo.encode("shift_jis")
    achados = []
    for num in sorted(csm3rom.ARCHIVE_OFFSETS):
        try:
            arc = csm3rom.open_archive(rom, num)
        except ValueError:
            continue
        for entry in arc.entries:
            if entry.is_empty:
                continue
            blob = arc.raw(entry.index)
            # tenta descomprimir; se nao for LZ77, usa cru
            data = blob
            if blob[:1] == b"\x10":
                try:
                    data = lz77.decompress(rom, entry.offset)
                except lz77.Lz77Error:
                    data = blob
            pos = data.find(raw)
            while pos != -1:
                achados.append((num, entry.index, pos))
                pos = data.find(raw, pos + 1)
    return achados


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    alvo = sys.argv[1]

    rom = csm3rom.load_rom(REPO / "baserom.gba")
    print("=" * 72)
    print(f'BUSCA POR "{alvo}"  (Shift-JIS: {alvo.encode("shift_jis").hex(" ")})')
    print("=" * 72)

    nos_scripts = buscar_nos_scripts(alvo)
    print(f"\n  1) nas strings do archive 2 (scripts): {len(nos_scripts)} ocorrencias")
    por_script = Counter(e["script"] for e in nos_scripts)
    for e in nos_scripts[:12]:
        print(f"      script {e['script']:4d} @0x{e['offset']:04X} "
              f"{e['opcode']}  \"{e['jp']}\"")
    if len(nos_scripts) > 12:
        print(f"      ... e mais {len(nos_scripts)-12}")
    if por_script:
        print(f"      distribuidas em {len(por_script)} scripts")

    nos_arcs = buscar_nos_archives(rom, alvo)
    fora_do_2 = [a for a in nos_arcs if a[0] != 2]
    print(f"\n  2) dentro de blobs de archives: {len(nos_arcs)} ocorrencias")
    por_archive = Counter(a[0] for a in nos_arcs)
    for num, n in sorted(por_archive.items()):
        marca = "  <-- FORA dos scripts" if num != 2 else ""
        print(f"      archive {num}: {n}{marca}")
    for num, idx, pos in fora_do_2[:10]:
        print(f"      archive {num} entrada {idx} @0x{pos:04X}")

    crus = buscar_na_rom_crua(rom, alvo)
    print(f"\n  3) nos bytes crus da ROM (nao comprimido): {len(crus)} ocorrencias")
    for pos in crus[:10]:
        print(f"      0x{pos:07X}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
