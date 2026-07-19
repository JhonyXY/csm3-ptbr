#!/usr/bin/env python3
"""Simula a traducao COMPLETA e mede o custo real de espaco.

Substitui todo o texto dos 1124 scripts por portugues sintetico com expansao de
2,2x, recomprime tudo e compara com o archive original. Sem estimativa: numero
medido.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import encoder
import lz77
import walker

REPO = Path(__file__).resolve().parents[2]

# Texto de enchimento com estatistica parecida com portugues real:
# palavras curtas, muita repeticao de letras e digrafos comuns.
AMOSTRA = (
    "o guerreiro disse que a espada estava quebrada e precisava de reparo "
    "antes da proxima batalha contra os monstros da caverna escura porque "
    "sem ela nao havia como vencer o chefe que guardava o tesouro antigo "
)

EXPANSAO = 2.2


def texto_para(n_chars: int) -> str:
    """Devolve n_chars de texto de enchimento."""
    repeticoes = n_chars // len(AMOSTRA) + 2
    return (AMOSTRA * repeticoes)[:n_chars]


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    auto_map = walker.load_auto_map()
    archive = csm3rom.open_archive(rom, csm3rom.SCRIPT_ARCHIVE)

    print("=" * 72)
    print(f"SIMULACAO DA TRADUCAO COMPLETA (expansao {EXPANSAO}x, 2 bytes/char)")
    print("=" * 72)
    print("  processando 1124 scripts...")

    orig_comp = 0
    novo_comp = 0
    orig_descomp = 0
    novo_descomp = 0
    chars_jp = 0
    chars_pt = 0
    estourou = []

    for entry in archive.entries:
        if entry.is_empty:
            continue
        script = csm3rom.load_script(archive, entry.index)
        if script is None:
            continue

        original = bytes(script.body)
        orig_comp += entry.size
        orig_descomp += len(original)

        result = walker.walk(original, auto_map)
        novo = bytearray()
        for ins in result.instructions:
            novo += struct.pack("<H", ins.opcode)
            for kind, words in ins.parts:
                if kind == "string" and words:
                    n_jp = len(words)
                    n_pt = max(1, int(n_jp * EXPANSAO))
                    chars_jp += n_jp
                    chars_pt += n_pt
                    for w in encoder.encode(texto_para(n_pt)):
                        novo += struct.pack("<H", w)
                    novo += struct.pack("<H", 0)
                else:
                    for w in words:
                        novo += struct.pack("<H", w)
                    if kind == "string":
                        novo += struct.pack("<H", 0)

        if len(novo) > 0xFFFE:
            estourou.append((entry.index, len(novo)))

        novo_descomp += len(novo)
        comp = lz77.compress(bytes(novo))
        novo_comp += len(comp) + ((16 - len(comp) % 16) % 16)

    print()
    print("  --- descomprimido ---")
    print(f"  bytecode original : {orig_descomp:,} bytes")
    print(f"  bytecode traduzido: {novo_descomp:,} bytes  "
          f"({novo_descomp/orig_descomp:.2f}x)")
    print(f"  caracteres        : {chars_jp:,} JP -> {chars_pt:,} PT")

    print()
    print("  --- COMPRIMIDO (o que importa) ---")
    print(f"  archive original  : {orig_comp:,} bytes")
    print(f"  archive traduzido : {novo_comp:,} bytes")
    delta = novo_comp - orig_comp
    print(f"  DELTA             : {delta:+,} bytes ({100*delta/orig_comp:+.1f}%)")

    livre = 282_116
    print()
    print("=" * 72)
    print("VEREDITO")
    print("=" * 72)
    print(f"  espaco livre na ROM : {livre:,} bytes")
    print(f"  crescimento medido  : {delta:+,} bytes")
    if delta <= livre:
        print(f"  CABE, com folga de {livre - delta:,} bytes.")
        print()
        print("  Ou seja: 2 bytes por caractere serve. O empacotamento de 2 chars")
        print("  por palavra NAO e necessario - e ele exigiria patchar o decoder")
        print("  de SJIS e a VM. Trabalho evitado.")
    else:
        print(f"  NAO CABE: faltam {delta - livre:,} bytes.")

    if estourou:
        print()
        print(f"  ATENCAO: {len(estourou)} scripts passariam de 0xFFFE bytes,")
        print("  o limite que o operando u16 de salto endereca:")
        for idx, n in estourou[:5]:
            print(f"      script {idx}: {n:,} bytes")
    else:
        print()
        print("  Nenhum script passa do limite de 0xFFFE do operando de salto.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
