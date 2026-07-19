#!/usr/bin/env python3
"""Diagnostico dos codigos de controle embutidos nas strings.

Despeja o contexto bruto das strings que nao decodificam e das palavras que nao
sao Shift-JIS valido, para revelar a estrutura das tags (quantos parametros cada
uma consome).
"""

from __future__ import annotations

import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import script_text
from script_text import is_sjis_pair, word_to_sjis

ROM_PATH = Path(__file__).resolve().parents[2] / "baserom.gba"


def annotate(word: int) -> str:
    """Descreve uma palavra: caractere Shift-JIS ou marcador de codigo."""
    if is_sjis_pair(word):
        pair = word_to_sjis(word)
        try:
            return f"'{pair.decode('shift_jis')}'"
        except UnicodeDecodeError:
            return "<sjis invalido>"
    return "<<CODIGO>>"


def main() -> int:
    rom = csm3rom.load_rom(ROM_PATH)

    all_runs = []
    for script in csm3rom.iter_scripts(rom):
        all_runs.extend(script_text.scan_text_runs(bytes(script.body), script.index))

    # --- 1. Strings que nao decodificam: mostra o stream cru --------------
    print("=" * 72)
    print("STRINGS QUE NAO DECODIFICAM - dump palavra a palavra")
    print("=" * 72)
    shown = 0
    for run in all_runs:
        try:
            run.decode()
            continue
        except UnicodeDecodeError:
            pass
        print(f"\n  script {run.script} @0x{run.text_offset:04X} marker 0x{run.marker:04X}")
        line = []
        for i, w in enumerate(run.words):
            line.append(f"{w:04X}{annotate(w)}")
        print("    " + " ".join(line))
        shown += 1
        if shown >= 10:
            break

    # --- 2. Contexto de cada palavra nao-SJIS ----------------------------
    print()
    print("=" * 72)
    print("CONTEXTO DAS PALAVRAS NAO-SJIS (o que vem antes e depois)")
    print("=" * 72)

    contexts: dict[int, list[tuple]] = defaultdict(list)
    for run in all_runs:
        for i, w in enumerate(run.words):
            if is_sjis_pair(w):
                continue
            before = run.words[max(0, i - 2) : i]
            after = run.words[i + 1 : i + 4]
            contexts[w].append((run.script, run.text_offset, i, before, after))

    for word in sorted(contexts, key=lambda w: -len(contexts[w]))[:14]:
        occurrences = contexts[word]
        print(f"\n  --- 0x{word:04X} ({len(occurrences)} ocorrencias) ---")

        # A palavra e sempre seguida do mesmo tipo de coisa? Isso revela se ela
        # consome parametro.
        next_is_sjis = sum(1 for _, _, _, _, a in occurrences if a and is_sjis_pair(a[0]))
        next_is_code = sum(1 for _, _, _, _, a in occurrences if a and not is_sjis_pair(a[0]))
        at_end = sum(1 for _, _, _, _, a in occurrences if not a)
        print(f"      seguida de SJIS: {next_is_sjis} | de codigo: {next_is_code} | fim: {at_end}")

        pos_first = sum(1 for _, _, i, _, _ in occurrences if i == 0)
        print(f"      aparece na posicao 0 da string: {pos_first}/{len(occurrences)}")

        for script, off, idx, before, after in occurrences[:4]:
            b = " ".join(f"{w:04X}{annotate(w)}" for w in before) or "(inicio)"
            a = " ".join(f"{w:04X}{annotate(w)}" for w in after) or "(fim)"
            print(f"      s{script} @0x{off:04X} idx{idx}: {b}  [{word:04X}]  {a}")

    # --- 3. O que vem DEPOIS do terminador de cada string ------------------
    # Se o byte seguinte for consistentemente um opcode valido, confirma que o
    # terminador realmente encerra a string.
    print()
    print("=" * 72)
    print("PALAVRA LOGO APOS O TERMINADOR (valida o fim da string)")
    print("=" * 72)
    after_term = Counter()
    for script in csm3rom.iter_scripts(rom):
        body = bytes(script.body)
        runs = script_text.scan_text_runs(body, script.index)
        for run in runs:
            pos = run.end_offset
            if pos + 2 <= len(body):
                after_term[struct.unpack_from("<H", body, pos)[0]] += 1
    total = sum(after_term.values())
    print(f"  total analisado: {total:,}")
    print("  20 mais comuns:")
    for word, n in after_term.most_common(20):
        hi = word >> 8
        tag = f"tabela hi=0x{hi:02X}" if hi <= 0x04 else "??? fora das tabelas"
        print(f"      0x{word:04X}  {n:6,d}x   {tag}")

    fora = sum(n for w, n in after_term.items() if (w >> 8) > 0x04)
    print(f"\n  palavras apos terminador que NAO sao opcode valido: {fora:,} "
          f"({100*fora/total:.2f}%)")
    if fora:
        print("  (indica strings cujo fim foi identificado errado)")
        for word, n in sorted(after_term.items(), key=lambda x: -x[1]):
            if (word >> 8) > 0x04:
                print(f"      0x{word:04X}  {n:,}x  {annotate(word)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
