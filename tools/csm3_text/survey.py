#!/usr/bin/env python3
"""Levantamento da ROM: valida a leitura dos archives, descomprime todos os
scripts e extrai as tabelas de despacho de opcode.

Nao modifica nada. Serve para provar que csm3rom.py/lz77.py entendem o formato
antes de qualquer tentativa de reinjecao.
"""

from __future__ import annotations

import json
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import lz77

ROM_PATH = Path(__file__).resolve().parents[2] / "baserom.gba"
OUT_DIR = Path(__file__).parent / "_out"

# Tabelas de despacho. O byte alto do opcode escolhe a tabela, o byte baixo e o
# indice. Limites derivados da contiguidade entre as tabelas (ver relatorio).
DISPATCH_TABLES = [
    ("hi=0x00", 0x0B716B4, 0x0B716F4),
    ("hi=0x01", 0x0B716F4, 0x0B71750),
    ("hi=0x02", 0x0B71750, 0x0B718B0),
    ("hi=0x03", 0x0B718B0, 0x0B71AEC),
    ("hi=0x04", 0x0B71AEC, 0x0B71D8C),
]


def dump_archives(rom: bytes) -> None:
    print("=" * 72)
    print("ARCHIVES")
    print("=" * 72)
    for num, base in sorted(csm3rom.ARCHIVE_OFFSETS.items()):
        arc = csm3rom.open_archive(rom, num)
        used = arc.used()
        total = sum(e.size for e in used)
        print(
            f"  archive {num} @ 0x{base:07X}: {arc.count:5d} slots, "
            f"{len(used):5d} usados, {total:9,d} bytes de payload"
        )


def dump_dispatch_tables(rom: bytes) -> dict:
    print()
    print("=" * 72)
    print("TABELAS DE DESPACHO DE OPCODE")
    print("=" * 72)
    tables = {}
    for name, start, end in DISPATCH_TABLES:
        count = (end - start) // 4
        entries = []
        for i in range(count):
            ptr = struct.unpack_from("<I", rom, start + i * 4)[0]
            entries.append(ptr)

        valid = sum(1 for p in entries if p == 0 or (0x08000000 <= p < 0x0A000000))
        thumb = sum(1 for p in entries if p and p & 1)
        nulls = sum(1 for p in entries if p == 0)
        print(
            f"  {name} @ 0x{start:07X}: {count:3d} entradas | "
            f"{valid:3d} validas, {thumb:3d} thumb, {nulls:3d} NULL"
        )
        if valid != count:
            bad = [
                (i, p)
                for i, p in enumerate(entries)
                if not (p == 0 or 0x08000000 <= p < 0x0A000000)
            ]
            print(f"      !! entradas invalidas: {bad[:5]}")
        tables[name] = entries
    return tables


def dump_scripts(rom: bytes) -> tuple[list, Counter]:
    print()
    print("=" * 72)
    print("SCRIPTS (archive 2)")
    print("=" * 72)
    arc = csm3rom.open_archive(rom, csm3rom.SCRIPT_ARCHIVE)

    ok = 0
    failures = []
    sizes = []
    header_tails = Counter()

    for entry in arc.entries:
        if entry.is_empty:
            continue
        try:
            script = csm3rom.load_script(arc, entry.index)
        except (ValueError, lz77.Lz77Error) as exc:
            failures.append((entry.index, str(exc)))
            continue
        ok += 1
        sizes.append(len(script.body))
        header_tails[script.header[8:]] += 1

    print(f"  descomprimidos e validados: {ok}")
    print(f"  falhas: {len(failures)}")
    for idx, msg in failures[:10]:
        print(f"      script {idx}: {msg}")
    if sizes:
        print(
            f"  bytecode: min {min(sizes):,} / mediana {sorted(sizes)[len(sizes)//2]:,} "
            f"/ max {max(sizes):,} bytes | total {sum(sizes):,}"
        )
    print(f"  variantes dos bytes 0x08-0x0F do header PSI3: {len(header_tails)}")
    for tail, n in header_tails.most_common(3):
        print(f"      {tail.hex()} -> {n} scripts")

    return failures, header_tails


def check_lz77_roundtrip(rom: bytes, sample: int = 40) -> None:
    """Comprime e descomprime de volta, para provar que o compressor e valido."""
    print()
    print("=" * 72)
    print(f"ROUND-TRIP DO COMPRESSOR LZ77 (amostra de {sample} scripts)")
    print("=" * 72)
    arc = csm3rom.open_archive(rom, csm3rom.SCRIPT_ARCHIVE)
    used = arc.used()
    step = max(1, len(used) // sample)

    ok = 0
    bad = []
    orig_total = 0
    ours_total = 0
    for entry in used[::step][:sample]:
        original = lz77.decompress(rom, entry.offset)
        recompressed = lz77.compress(original)
        try:
            back = lz77.decompress(recompressed)
        except lz77.Lz77Error as exc:
            bad.append((entry.index, f"nao descomprime: {exc}"))
            continue
        if back != original:
            bad.append((entry.index, "conteudo diferente apos round-trip"))
            continue
        ok += 1
        orig_total += entry.size
        ours_total += len(recompressed)

    print(f"  round-trip ok: {ok}/{ok + len(bad)}")
    for idx, msg in bad[:5]:
        print(f"      script {idx}: {msg}")
    if ok and orig_total:
        ratio = ours_total / orig_total
        print(
            f"  tamanho comprimido vs original: {ours_total:,} / {orig_total:,} "
            f"= {ratio:.3f}x"
        )
        if ratio > 1.0:
            print("  (nosso compressor e mais folgado que o original - previsto)")


def main() -> int:
    if not ROM_PATH.exists():
        print(f"ERRO: {ROM_PATH} nao encontrado", file=sys.stderr)
        return 1

    rom = csm3rom.load_rom(ROM_PATH)
    OUT_DIR.mkdir(exist_ok=True)

    dump_archives(rom)
    tables = dump_dispatch_tables(rom)
    failures, _ = dump_scripts(rom)
    check_lz77_roundtrip(rom)

    handlers = {}
    for name, entries in tables.items():
        for i, ptr in enumerate(entries):
            if ptr:
                handlers.setdefault(ptr & ~1, []).append(f"{name}[0x{i:02X}]")
    (OUT_DIR / "handlers.json").write_text(
        json.dumps(
            {f"0x{addr:08X}": sorted(ops) for addr, ops in sorted(handlers.items())},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print(f"handlers unicos: {len(handlers)} -> {OUT_DIR / 'handlers.json'}")
    print("=" * 72)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
