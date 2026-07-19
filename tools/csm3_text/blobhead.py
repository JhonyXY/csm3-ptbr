#!/usr/bin/env python3
"""Testa a hipotese de que o inicio do blob e uma TABELA, nao codigo.

Alvos de salto identicos (0x00C0, 0x00C8, 0x00CC) aparecendo em scripts
diferentes sugerem que o codigo nao comeca no offset 0 do corpo - haveria uma
tabela de pontos de entrada antes dele.
"""

from __future__ import annotations

import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import walker

ROM_PATH = Path(__file__).resolve().parents[2] / "baserom.gba"


def main() -> int:
    rom = csm3rom.load_rom(ROM_PATH)

    print("=" * 72)
    print("PRIMEIRAS PALAVRAS DO CORPO DE ALGUNS SCRIPTS")
    print("=" * 72)
    scripts = []
    for script in csm3rom.iter_scripts(rom):
        scripts.append(script)
        if len(scripts) >= 400:
            break

    for script in scripts[:4]:
        body = bytes(script.body)
        print(f"\n  --- script {script.index} ({len(body)} bytes) ---")
        for row in range(8):
            off = row * 16
            if off >= len(body):
                break
            words = struct.unpack_from("<8H", body, off)
            hexs = " ".join(f"{w:04X}" for w in words)
            print(f"      +0x{off:04X}: {hexs}")

    # Se o inicio for uma tabela de offsets, os valores devem ser pequenos,
    # pares, crescentes e menores que o tamanho do corpo.
    print()
    print("=" * 72)
    print("O INICIO SE COMPORTA COMO TABELA DE OFFSETS?")
    print("=" * 72)
    plausible = 0
    checked = 0
    first_word = Counter()
    for script in scripts:
        body = bytes(script.body)
        if len(body) < 0x20:
            continue
        checked += 1
        words = struct.unpack_from("<8H", body, 0)
        first_word[words[0]] += 1
        # todos pares, nao nulos, dentro do corpo, e crescentes?
        vals = [w for w in words if w]
        if vals and all(v % 2 == 0 for v in vals) and all(v < len(body) for v in vals):
            plausible += 1

    print(f"  scripts checados: {checked}")
    print(f"  com as 8 primeiras palavras parecendo offsets validos: {plausible} "
          f"({100*plausible/max(1,checked):.1f}%)")
    print("  primeira palavra do corpo, valores mais comuns:")
    for w, n in first_word.most_common(8):
        print(f"      0x{w:04X}: {n}x")

    # Onde os alvos de salto se concentram? Se houver um piso comum, ele indica
    # onde o codigo comeca de verdade.
    print()
    print("=" * 72)
    print("MENOR ALVO DE SALTO POR SCRIPT (piso do codigo)")
    print("=" * 72)
    auto_map = walker.load_auto_map()
    floors = Counter()
    for script in scripts:
        body = bytes(script.body)
        result = walker.walk(body, auto_map)
        if result.jump_targets:
            floors[min(result.jump_targets)] += 1
    print("  valores mais comuns do menor alvo:")
    for off, n in floors.most_common(12):
        print(f"      0x{off:04X}: {n}x")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
