#!/usr/bin/env python3
"""Inventario de caracteres: descobre empiricamente o que e texto e o que e
control code dentro das strings.

Em vez de assumir quais codigos sao tags de controle, extrai TODAS as strings do
jogo e classifica cada palavra distinta que aparece nelas. Codigos que nao
decodificam como Shift-JIS valido, ou que caem em faixas suspeitas (grego, NEC
special), sao candidatos a control code.
"""

from __future__ import annotations

import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import script_text
from script_text import is_sjis_pair, word_to_sjis

ROM_PATH = Path(__file__).resolve().parents[2] / "baserom.gba"
OUT_DIR = Path(__file__).parent / "_out"

# Faixas Shift-JIS que o jogo pode estar reaproveitando como codigo de controle.
SUSPECT_RANGES = [
    ("grego maiusculo", 0x839F, 0x83B6),
    ("grego minusculo", 0x83BF, 0x83D6),
    ("cirilico", 0x8440, 0x8491),
    ("NEC especiais (0x87)", 0x8740, 0x879C),
    ("caixas/linhas (0x84)", 0x849F, 0x84BE),
]


def in_suspect_range(sjis_be: int) -> str | None:
    for name, lo, hi in SUSPECT_RANGES:
        if lo <= sjis_be <= hi:
            return name
    return None


def main() -> int:
    rom = csm3rom.load_rom(ROM_PATH)
    OUT_DIR.mkdir(exist_ok=True)

    all_runs = []
    marker_counts = Counter()
    scripts_with_text = 0

    for script in csm3rom.iter_scripts(rom):
        runs = script_text.scan_text_runs(bytes(script.body), script.index)
        if runs:
            scripts_with_text += 1
        for r in runs:
            marker_counts[r.marker] += 1
        all_runs.extend(runs)

    print("=" * 72)
    print("STRINGS ENCONTRADAS")
    print("=" * 72)
    print(f"  scripts com texto : {scripts_with_text}")
    print(f"  strings           : {len(all_runs):,}")
    total_words = sum(len(r.words) for r in all_runs)
    print(f"  palavras de texto : {total_words:,}")
    print("  por marcador:")
    for marker, n in marker_counts.most_common():
        print(f"      0x{marker:04X}: {n:,}")

    freq = script_text.classify_words(all_runs)
    print()
    print("=" * 72)
    print("INVENTARIO DE PALAVRAS DISTINTAS DENTRO DAS STRINGS")
    print("=" * 72)
    print(f"  palavras distintas: {len(freq):,}")

    valid, invalid, suspect = [], [], []
    for word, count in freq.items():
        pair = word_to_sjis(word)
        sjis_be = (pair[0] << 8) | pair[1]
        if not is_sjis_pair(word):
            invalid.append((word, count))
            continue
        hit = in_suspect_range(sjis_be)
        if hit:
            suspect.append((word, count, hit))
        else:
            valid.append((word, count))

    print(f"  Shift-JIS normal  : {len(valid):,} distintas")
    print(f"  faixa suspeita    : {len(suspect):,} distintas")
    print(f"  NAO e Shift-JIS   : {len(invalid):,} distintas")

    if invalid:
        print()
        print("  --- palavras que NAO decodificam como Shift-JIS ---")
        print("  (sao control codes quase com certeza)")
        for word, count in sorted(invalid, key=lambda x: -x[1])[:40]:
            pair = word_to_sjis(word)
            print(
                f"      u16 0x{word:04X}  bytes {pair.hex(' ')}  "
                f"{count:6,d}x"
            )

    if suspect:
        print()
        print("  --- palavras em faixas suspeitas (decodificam, mas provavelmente sao tags) ---")
        by_range = {}
        for word, count, name in suspect:
            by_range.setdefault(name, []).append((word, count))
        for name, items in by_range.items():
            total = sum(c for _, c in items)
            print(f"      {name}: {len(items)} distintas, {total:,} ocorrencias")
            for word, count in sorted(items, key=lambda x: -x[1])[:12]:
                pair = word_to_sjis(word)
                try:
                    ch = pair.decode("shift_jis")
                except UnicodeDecodeError:
                    ch = "?"
                print(
                    f"          u16 0x{word:04X}  sjis {pair.hex(' ')}  "
                    f"'{ch}'  {count:6,d}x"
                )

    # Prova de que a decodificacao e reversivel sem perda.
    print()
    print("=" * 72)
    print("ROUND-TRIP SHIFT-JIS (decode -> encode)")
    print("=" * 72)
    ok = 0
    failed_decode = []
    mismatched = []
    for run in all_runs:
        raw = run.raw
        try:
            text = raw.decode("shift_jis")
        except UnicodeDecodeError as exc:
            failed_decode.append((run.script, run.text_offset, str(exc)))
            continue
        if text.encode("shift_jis") != raw:
            mismatched.append((run.script, run.text_offset))
            continue
        ok += 1

    print(f"  round-trip perfeito : {ok:,} / {len(all_runs):,}")
    print(f"  falha ao decodificar: {len(failed_decode):,}")
    print(f"  reencode divergente : {len(mismatched):,}")
    for s, off, msg in failed_decode[:8]:
        print(f"      script {s} @0x{off:04X}: {msg}")

    # Amostra legivel.
    print()
    print("=" * 72)
    print("AMOSTRA")
    print("=" * 72)
    shown = 0
    for run in all_runs:
        if len(run.words) < 8:
            continue
        try:
            text = run.decode()
        except UnicodeDecodeError:
            continue
        print(f"  script {run.script:4d} @0x{run.text_offset:04X} "
              f"marker 0x{run.marker:04X}: {text}")
        shown += 1
        if shown >= 12:
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
