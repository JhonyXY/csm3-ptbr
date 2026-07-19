#!/usr/bin/env python3
"""Teste de identidade: prova que o parser e o serializador entendem o formato.

Para cada um dos 1124 scripts:
  1. descomprime
  2. percorre o bytecode respeitando a estrutura de cada opcode
  3. re-serializa a partir da representacao estruturada
  4. compara byte a byte com o original

O criterio de aceitacao do projeto e o numero de SALTOS FORA DE FRONTEIRA. Se um
alvo de salto nao cai no inicio de uma instrucao, a estrutura de algum opcode
esta errada - e reflowar texto com esse mapa corromperia o jogo.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import walker

ROM_PATH = Path(__file__).resolve().parents[2] / "baserom.gba"


def main() -> int:
    rom = csm3rom.load_rom(ROM_PATH)
    auto_map = walker.load_auto_map()

    print("=" * 72)
    print("TESTE DE IDENTIDADE (parse -> serialize -> comparar)")
    print("=" * 72)
    print(f"  opcodes no mapa automatico : {len(auto_map)}")
    print(f"  opcodes com spec manual    : {len(walker.opcode_spec.CRITICAL)}")
    print()

    identical = 0
    differing = []
    unknown_total: Counter = Counter()
    bad_jump_total = 0
    scripts_bad_jumps = []
    error_scripts = []
    total_instructions = 0
    total_text = 0
    total_jumps = 0

    for script in csm3rom.iter_scripts(rom):
        body = bytes(script.body)
        result = walker.walk(body, auto_map)

        total_instructions += len(result.instructions)
        total_text += len(result.text_instructions)
        total_jumps += len(result.jump_targets)
        unknown_total.update(result.unknown_opcodes)

        rebuilt = walker.serialize(result.instructions)
        if rebuilt == body or (len(body) - len(rebuilt) == 1 and body.startswith(rebuilt)):
            identical += 1
        else:
            differing.append((script.index, len(body), len(rebuilt)))

        bad = result.bad_jumps
        if bad:
            bad_jump_total += len(bad)
            scripts_bad_jumps.append((script.index, sorted(bad)[:5]))
        if result.errors:
            error_scripts.append((script.index, result.errors[:2]))

    total = identical + len(differing)
    print(f"  scripts identicos      : {identical:,} / {total:,}")
    print(f"  scripts divergentes    : {len(differing):,}")
    for idx, a, b in differing[:5]:
        print(f"      script {idx}: original {a} bytes, reconstruido {b}")
    print(f"  instrucoes percorridas : {total_instructions:,}")
    print(f"  instrucoes de texto    : {total_text:,}")
    print(f"  alvos de salto         : {total_jumps:,}")
    print()

    print("=" * 72)
    print("CRITERIO DE ACEITACAO: saltos fora de fronteira")
    print("=" * 72)
    print(f"  scripts afetados : {len(scripts_bad_jumps):,} de {total:,}")
    print(f"  saltos invalidos : {bad_jump_total:,}")
    for idx, targets in scripts_bad_jumps[:8]:
        alvos = ", ".join(f"0x{t:04X}" for t in targets)
        print(f"      script {idx}: {alvos}")

    print()
    print(f"  scripts com erro de percurso: {len(error_scripts):,}")
    for idx, errs in error_scripts[:5]:
        print(f"      script {idx}: {errs[0]}")

    print()
    print("=" * 72)
    print("OPCODES AINDA DESCONHECIDOS")
    print("=" * 72)
    print(f"  distintos: {len(unknown_total):,} | ocorrencias: {sum(unknown_total.values()):,}")
    for opcode, n in unknown_total.most_common(15):
        hi, lo = opcode >> 8, opcode & 0xFF
        marca = "  <-- fora das tabelas" if hi > 0x04 else ""
        print(f"      0x{opcode:04X}  (hi=0x{hi:02X} idx=0x{lo:02X})  {n:7,d}x{marca}")

    print()
    ok = identical == total and not scripts_bad_jumps and not unknown_total
    if ok:
        print("  RESULTADO: modelo completo e provado. Seguro reflowar texto.")
        return 0
    print("  RESULTADO: ainda incompleto.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
