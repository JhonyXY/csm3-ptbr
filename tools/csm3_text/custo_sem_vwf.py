#!/usr/bin/env python3
"""Quanto custa NAO ter VWF?

Mede, sobre as 20.192 falas reais, quantas caixas extras a traducao precisaria
com 18 caracteres por linha (12px fixos) contra 26 (VWF), em varios cenarios de
expansao. Tambem confere se a estrutura do bytecode permite inserir caixas.
"""

from __future__ import annotations

import json
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import walker

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"

LINHAS = 3
LARG_FIXA = 18
LARG_VWF = 26


def main() -> int:
    dados = json.loads((OUT / "falas_originais.json").read_text(encoding="utf-8"))
    falas = dados["falas"]
    chars = [f["chars"] for f in falas if f["chars"] > 0]

    print("=" * 72)
    print("DISTRIBUICAO REAL DAS FALAS")
    print("=" * 72)
    print(f"  falas com texto: {len(chars):,}")
    faixas = [(0, 9), (10, 19), (20, 29), (30, 39), (40, 53)]
    for lo, hi in faixas:
        n = sum(1 for c in chars if lo <= c <= hi)
        barra = "#" * (n * 44 // max(1, len(chars)) * 4)
        print(f"      {lo:2d}-{hi:2d} chars: {n:6,d} ({100*n/len(chars):4.1f}%) {barra}")

    print()
    print("=" * 72)
    print("CAIXAS NECESSARIAS POR CENARIO DE EXPANSAO")
    print("=" * 72)
    cap_fixa = LINHAS * LARG_FIXA
    cap_vwf = LINHAS * LARG_VWF
    print(f"  capacidade: {cap_fixa} chars/caixa sem VWF, {cap_vwf} com VWF")
    print()
    print(f"  {'expansao':>9} | {'sem VWF: extras':>16} | {'com VWF: extras':>16} | {'diferenca':>10}")
    print(f"  {'-'*9}-+-{'-'*16}-+-{'-'*16}-+-{'-'*10}")

    for exp in (1.6, 1.8, 2.0, 2.2, 2.5):
        extras_fixa = sum(max(0, -(-int(c * exp) // cap_fixa) - 1) for c in chars)
        extras_vwf = sum(max(0, -(-int(c * exp) // cap_vwf) - 1) for c in chars)
        print(f"  {exp:9.1f} | {extras_fixa:16,d} | {extras_vwf:16,d} | "
              f"{extras_fixa-extras_vwf:10,d}")

    print()
    print("  'extras' = caixas ADICIONAIS que o jogador teria que avancar.")
    print("  Uma caixa extra = um toque a mais no botao naquele dialogo.")

    # --- quanto da para encurtar na traducao? ---
    print()
    print("=" * 72)
    print("E SE A TRADUCAO FOR MAIS ENXUTA?")
    print("=" * 72)
    print("  As 43 strings de sistema que traduzi encurtando de proposito deram")
    print("  expansao de 1,19x. Uma traducao 'apertada' fica nessa faixa.")
    print()
    for exp in (1.2, 1.4, 1.6):
        estoura = sum(1 for c in chars if c * exp > cap_fixa)
        extras = sum(max(0, -(-int(c * exp) // cap_fixa) - 1) for c in chars)
        print(f"      expansao {exp:.1f}x sem VWF: {estoura:,} falas estouram "
              f"({100*estoura/len(chars):.1f}%), {extras:,} caixas extras")

    # --- a estrutura permite inserir caixa? ---
    print()
    print("=" * 72)
    print("DA PARA INSERIR CAIXA NOVA NO BYTECODE?")
    print("=" * 72)
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    auto_map = walker.load_auto_map()

    depois_do_bloco = Counter()
    blocos_por_tamanho = Counter()

    for script in csm3rom.iter_scripts(rom):
        result = walker.walk(bytes(script.body), auto_map)
        linhas_bloco = 0
        anterior_fim = None
        for ins in result.instructions:
            if ins.is_text and ins.opcode in (0x0308, 0x0363):
                if anterior_fim is not None and ins.offset != anterior_fim:
                    if linhas_bloco:
                        blocos_por_tamanho[linhas_bloco] += 1
                    linhas_bloco = 0
                linhas_bloco += 1
                anterior_fim = ins.offset + ins.size
            else:
                if linhas_bloco:
                    blocos_por_tamanho[linhas_bloco] += 1
                    if anterior_fim is not None and ins.offset == anterior_fim:
                        depois_do_bloco[ins.opcode] += 1
                    linhas_bloco = 0
                anterior_fim = None

    print("  opcode que fecha um bloco de fala:")
    total = sum(depois_do_bloco.values())
    for op, n in depois_do_bloco.most_common(6):
        print(f"      0x{op:04X}: {n:6,d} ({100*n/total:5.1f}%)")

    print()
    print("  Se um unico opcode dominar, ele e o 'mostra a caixa e espera'.")
    print("  Inserir caixa vira: repetir [0x0308 texto] + esse opcode.")
    print("  O injetor ja realoca os saltos quando o blob cresce.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
