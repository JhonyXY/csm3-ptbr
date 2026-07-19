#!/usr/bin/env python3
"""As 41.961 strings sao falas ou linhas quebradas de falas maiores?

Se forem linhas quebradas, traduzir uma a uma e adivinhacao: o modelo nao ve a
frase inteira. A resposta muda a arquitetura da Fase 1.

Sinais de que uma sequencia de 0x0308 forma UMA fala:
  - sao consecutivas no bytecode, sem opcode de "esperar input" entre elas
  - a linha termina sem pontuacao final (indica continuacao)
  - o padding de centralizacao muda entre linhas do mesmo bloco
"""

from __future__ import annotations

import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import walker

REPO = Path(__file__).resolve().parents[2]

PONTO_FINAL = "。？！…♪"
IDEOGRAPHIC_SPACE = "　"

# Opcodes de FALA (linhas de uma mesma mensagem, devem ser agrupadas) contra
# opcodes de ITEM DE MENU (cada um e uma opcao independente, nao agrupar).
OPS_FALA = {0x0308, 0x0363, 0x0311, 0x0317}
OPS_MENU = {0x0314, 0x030D, 0x0307, 0x030B, 0x0316}


def decodificar(words: list[int]) -> str | None:
    raw = bytearray()
    for w in words:
        raw += bytes((w & 0xFF, w >> 8))
    try:
        return bytes(raw).decode("shift_jis")
    except UnicodeDecodeError:
        return None


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    auto_map = walker.load_auto_map()

    blocos = []            # sequencias de texto consecutivas
    entre_texto = Counter()  # que opcode aparece entre duas falas
    total_linhas = 0

    for script in csm3rom.iter_scripts(rom):
        result = walker.walk(bytes(script.body), auto_map)
        atual = []
        anterior_fim = None

        for ins in result.instructions:
            if ins.is_text:
                total_linhas += 1
                texto = decodificar(ins.text_words or [])
                if texto is None:
                    continue
                # Itens de menu sao opcoes independentes: nunca agrupar.
                if ins.opcode in OPS_MENU:
                    if atual:
                        blocos.append(atual)
                        atual = []
                    blocos.append([(script.index, ins.offset, ins.opcode, texto)])
                    anterior_fim = ins.offset + ins.size
                    continue
                if anterior_fim is not None and ins.offset != anterior_fim:
                    # houve instrucao entre as duas falas
                    if atual:
                        blocos.append(atual)
                        atual = []
                atual.append((script.index, ins.offset, ins.opcode, texto))
                anterior_fim = ins.offset + ins.size
            else:
                if atual and anterior_fim is not None and ins.offset == anterior_fim:
                    entre_texto[ins.opcode] += 1
                if atual:
                    blocos.append(atual)
                    atual = []
                anterior_fim = None
        if atual:
            blocos.append(atual)

    print("=" * 72)
    print("AS STRINGS SAO FALAS OU LINHAS?")
    print("=" * 72)
    print(f"  linhas de texto totais : {total_linhas:,}")
    print(f"  blocos consecutivos    : {len(blocos):,}")
    tam = Counter(len(b) for b in blocos)
    print(f"  reducao se agrupar     : {total_linhas:,} -> {len(blocos):,} "
          f"({total_linhas/max(1,len(blocos)):.1f} linhas por bloco)")

    print("\n  tamanho dos blocos (linhas por bloco):")
    for n in sorted(tam)[:10]:
        barra = "#" * min(46, tam[n] * 46 // max(tam.values()))
        print(f"      {n:2d} linha(s): {tam[n]:6,d}  {barra}")

    print("\n  opcode que aparece logo apos um bloco de texto:")
    for op, n in entre_texto.most_common(8):
        print(f"      0x{op:04X}: {n:,}")

    # Quantas linhas terminam SEM pontuacao final? Indica continuacao.
    sem_pont = com_pont = 0
    for b in blocos:
        for _, _, _, texto in b[:-1]:   # todas menos a ultima do bloco
            limpo = texto.strip(IDEOGRAPHIC_SPACE)
            if not limpo:
                continue
            if limpo[-1] in PONTO_FINAL:
                com_pont += 1
            else:
                sem_pont += 1
    total = sem_pont + com_pont
    if total:
        print()
        print("  linhas NAO-finais de um bloco:")
        print(f"      terminam sem pontuacao : {sem_pont:,} ({100*sem_pont/total:.1f}%)")
        print(f"      terminam com pontuacao : {com_pont:,} ({100*com_pont/total:.1f}%)")
        print("      (alto % sem pontuacao = sao continuacao, nao falas soltas)")

    print()
    print("=" * 72)
    print("AMOSTRA DE BLOCOS COM VARIAS LINHAS")
    print("=" * 72)
    mostrados = 0
    for b in blocos:
        if len(b) < 4:
            continue
        script, off, _, _ = b[0]
        print(f"\n  --- script {script} @0x{off:04X} ({len(b)} linhas) ---")
        for _, _, op, texto in b:
            print(f"      0x{op:04X}  {texto}")
        junto = "".join(t.strip(IDEOGRAPHIC_SPACE) for _, _, _, t in b)
        print(f"      => junto: {junto}")
        mostrados += 1
        if mostrados >= 4:
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
