#!/usr/bin/env python3
"""Mede a expansao real japones -> portugues, em vez de estimar.

Usa as 43 strings de sistema ja traduzidas como amostra, extrapola para os
382.696 caracteres de dialogo e comprime de verdade para saber o custo final.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import encoder
import lz77
import walker

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"


def main() -> int:
    sysd = json.loads((OUT / "sysstrings.json").read_text(encoding="utf-8"))
    pares = [(e["jp"], e["pt"]) for e in sysd["strings"] if e.get("pt")]

    jp_chars = sum(len(jp) for jp, _ in pares)
    pt_chars = sum(len(pt) for _, pt in pares)
    ratio = pt_chars / jp_chars

    print("=" * 72)
    print("EXPANSAO MEDIDA (amostra: as 43 strings de sistema traduzidas)")
    print("=" * 72)
    print(f"  caracteres japoneses : {jp_chars:,}")
    print(f"  caracteres portugues : {pt_chars:,}")
    print(f"  razao PT/JP          : {ratio:.2f}x")
    print()
    print("  as maiores expansoes:")
    piores = sorted(pares, key=lambda p: -(len(p[1]) / max(1, len(p[0]))))[:5]
    for jp, pt in piores:
        print(f"      {len(jp):2d} -> {len(pt):2d} ch  ({len(pt)/len(jp):.1f}x)  "
              f"\"{jp}\" -> \"{pt}\"")

    # Nota importante: essa amostra e enviesada para BAIXO, porque encurtei as
    # frases de proposito para caber na caixa de 12px fixos.
    print()
    print("  ATENCAO: esta amostra esta ENVIESADA PARA BAIXO - encurtei as")
    print("  traducoes de proposito para caberem na caixa sem VWF.")
    print("  Uma traducao natural, sem essa amarra, seria maior.")

    print()
    print("=" * 72)
    print("EXTRAPOLACAO PARA O DIALOGO (382.696 caracteres japoneses)")
    print("=" * 72)

    dialogo_jp = 382_696
    for nome, r in (("medida (encurtada)", ratio), ("natural (estimada)", 2.2)):
        pt = int(dialogo_jp * r)
        b2 = pt * 2
        b1 = pt
        print(f"\n  razao {r:.2f}x - {nome}: {pt:,} caracteres")
        print(f"      em 2 bytes/char: {b2:,} bytes descomprimidos")
        print(f"      em 1 byte/char : {b1:,} bytes descomprimidos")

    jp_bytes = dialogo_jp * 2
    print(f"\n  hoje o japones ocupa: {jp_bytes:,} bytes descomprimidos")

    # --- o teste que importa: comprimir texto latino de verdade -------------
    print()
    print("=" * 72)
    print("TAXA DE COMPRESSAO REAL DO TEXTO LATINO")
    print("=" * 72)

    rom = csm3rom.load_rom(REPO / "baserom.gba")
    auto_map = walker.load_auto_map()
    archive = csm3rom.open_archive(rom, csm3rom.SCRIPT_ARCHIVE)

    # Pega um script de dialogo grande e mede japones vs latino equivalente.
    alvo = None
    for entry in archive.entries:
        if entry.is_empty:
            continue
        s = csm3rom.load_script(archive, entry.index)
        if s and len(s.body) > 15000:
            alvo = s
            break

    if alvo:
        original = bytes(alvo.body)
        comp_jp = lz77.compress(original)
        print(f"  script {alvo.index}: {len(original):,} bytes -> "
              f"{len(comp_jp):,} comprimidos ({len(comp_jp)/len(original):.3f}x)")

        # Substitui todo o texto por latino do mesmo tamanho em caracteres.
        result = walker.walk(original, auto_map)
        amostra = "Lorem ipsum dolor sit amet consectetur adipiscing elit sed"
        novo = bytearray()
        for ins in result.instructions:
            novo += struct.pack("<H", ins.opcode)
            for kind, words in ins.parts:
                if kind == "string" and words:
                    texto = (amostra * 5)[: len(words)]
                    subs = encoder.encode(texto)
                    for w in subs:
                        novo += struct.pack("<H", w)
                    novo += struct.pack("<H", 0)
                else:
                    for w in words:
                        novo += struct.pack("<H", w)
                    if kind == "string":
                        novo += struct.pack("<H", 0)

        comp_pt = lz77.compress(bytes(novo))
        print(f"  mesmo script com texto latino (mesma contagem de chars):")
        print(f"      {len(novo):,} bytes -> {len(comp_pt):,} comprimidos "
              f"({len(comp_pt)/len(novo):.3f}x)")
        print(f"      delta comprimido: {len(comp_pt)-len(comp_jp):+,} bytes "
              f"({100*(len(comp_pt)-len(comp_jp))/len(comp_jp):+.1f}%)")
        print()
        print("  O latino comprime MUITO melhor: alfabeto pequeno e repetitivo.")

    print()
    print("=" * 72)
    print("ESPACO DISPONIVEL")
    print("=" * 72)
    print(f"  archive 2 comprimido hoje : 1,737,488 bytes")
    print(f"  padding livre no fim      :   282,116 bytes")
    print(f"  ROM                       : 33,554,432 bytes = MAXIMO do GBA")
    print()
    print("  O teto de 32 MiB e do hardware (espaco 0x08000000-0x09FFFFFF).")
    print("  Nem o linker nem compressao nenhuma contornam isso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
