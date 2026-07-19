#!/usr/bin/env python3
"""Mapeia quais falas ja estao dentro de uma bifurcacao por genero.

O jogo guarda o genero do protagonista na variavel de script 0x182 e usa o
opcode 0x0002 (salto condicional) para separar as falas. A expressao tipica e:

    [0x0002 0x0182]  empilha a variavel 0x182
    [0x0001 0x0000]  empilha o literal 0
    [0x008B]         compara (igualdade)
    [0x0000]         fim da expressao

O opcode 0x0002 SALTA quando a expressao da zero. Como a expressao e
"genero == 0", ela vale 1 para masculino: masculino cai no fall-through e
feminino salta. Logo o trecho entre o salto e o alvo e o texto MASCULINO.

Saber isso separa as falas em tres grupos, e cada um exige um tratamento
diferente na traducao.
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
from script_text import word_to_sjis

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"

VAR_GENERO = 0x0182
VAR_PARCEIRO = 0x0183
TOKEN_VAR = 0x0002       # empilha variavel
OPCODE_SALTO_COND = 0x0002


def expressao_le_variavel(words: list[int], var: int) -> bool:
    """A expressao RPN consulta esta variavel?"""
    i = 0
    while i < len(words):
        tok = words[i]
        if tok == 0:
            break
        if tok in (0x0001, 0x0002, 0x0003):
            if i + 1 < len(words):
                if tok == TOKEN_VAR and words[i + 1] == var:
                    return True
            i += 2
        else:
            i += 1
    return False


def decodificar(words: list[int]) -> str:
    raw = bytearray()
    for w in words:
        raw += word_to_sjis(w)
    try:
        return bytes(raw).decode("shift_jis")
    except UnicodeDecodeError:
        return ""


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    auto_map = walker.load_auto_map()

    total_falas = 0
    em_ramo_genero = 0
    em_ramo_parceiro = 0
    fora = 0
    ramos_genero = 0
    scripts_com_genero = set()
    exemplos = []

    for script in csm3rom.iter_scripts(rom):
        body = bytes(script.body)
        result = walker.walk(body, auto_map)

        # Faixas [inicio, fim) cobertas por um ramo de genero.
        faixas_genero = []
        faixas_parceiro = []

        for ins in result.instructions:
            if ins.opcode != OPCODE_SALTO_COND:
                continue
            # seq = [word (alvo), expr]
            alvo = None
            expr = None
            for kind, palavras in ins.parts:
                if kind == "word" and alvo is None:
                    alvo = palavras[0] & ~1
                elif kind == "expr":
                    expr = palavras
            if alvo is None or expr is None:
                continue
            fim_ins = ins.offset + ins.size
            if alvo <= fim_ins:
                continue  # salto para tras: laco, nao bifurcacao
            if expressao_le_variavel(expr, VAR_GENERO):
                faixas_genero.append((fim_ins, alvo))
                ramos_genero += 1
                scripts_com_genero.add(script.index)
            elif expressao_le_variavel(expr, VAR_PARCEIRO):
                faixas_parceiro.append((fim_ins, alvo))

        def dentro(off: int, faixas) -> bool:
            return any(a <= off < b for a, b in faixas)

        # Conta as falas (agrupando linhas contiguas como no export_falas).
        anterior_fim = None
        bloco_inicio = None
        for ins in result.instructions:
            if not ins.is_text:
                if bloco_inicio is not None:
                    total_falas += 1
                    if dentro(bloco_inicio, faixas_genero):
                        em_ramo_genero += 1
                    elif dentro(bloco_inicio, faixas_parceiro):
                        em_ramo_parceiro += 1
                    else:
                        fora += 1
                    bloco_inicio = None
                anterior_fim = None
                continue
            if anterior_fim is not None and ins.offset != anterior_fim:
                if bloco_inicio is not None:
                    total_falas += 1
                    if dentro(bloco_inicio, faixas_genero):
                        em_ramo_genero += 1
                    elif dentro(bloco_inicio, faixas_parceiro):
                        em_ramo_parceiro += 1
                    else:
                        fora += 1
                bloco_inicio = None
            if bloco_inicio is None:
                bloco_inicio = ins.offset
                if dentro(ins.offset, faixas_genero) and len(exemplos) < 6:
                    texto = decodificar(ins.text_words or [])
                    if texto:
                        exemplos.append((script.index, ins.offset, texto))
            anterior_fim = ins.offset + ins.size
        if bloco_inicio is not None:
            total_falas += 1
            if dentro(bloco_inicio, faixas_genero):
                em_ramo_genero += 1
            elif dentro(bloco_inicio, faixas_parceiro):
                em_ramo_parceiro += 1
            else:
                fora += 1

    print("=" * 72)
    print("BIFURCACOES POR GENERO NO BYTECODE")
    print("=" * 72)
    print(f"  ramos condicionais lendo a var 0x182 : {ramos_genero:,}")
    print(f"  scripts que bifurcam por genero      : {len(scripts_com_genero):,} de 1.124")

    print()
    print("=" * 72)
    print("COMO AS FALAS SE DISTRIBUEM")
    print("=" * 72)
    print(f"  falas totais                    : {total_falas:,}")
    print(f"  dentro de ramo de GENERO        : {em_ramo_genero:,} "
          f"({100*em_ramo_genero/max(1,total_falas):.1f}%)")
    print(f"  dentro de ramo de PARCEIRO      : {em_ramo_parceiro:,} "
          f"({100*em_ramo_parceiro/max(1,total_falas):.1f}%)")
    print(f"  fora de qualquer ramo           : {fora:,} "
          f"({100*fora/max(1,total_falas):.1f}%)")

    print()
    print("  --- amostra de falas ja dentro de ramo de genero ---")
    for s, off, texto in exemplos:
        print(f"      script {s} @0x{off:04X}: {texto}")

    print()
    print("=" * 72)
    print("O QUE ISSO SIGNIFICA PARA A TRADUCAO")
    print("=" * 72)
    print(f"  {em_ramo_genero:,} falas ja tem variante masculina e feminina separadas:")
    print("      traduza cada ramo com o registro correspondente. Sem trabalho extra.")
    print()
    print(f"  {fora:,} falas sao compartilhadas pelos dois generos:")
    print("      o portugues so precisa de ramo NOVO onde houver concordancia com")
    print("      o jogador. Estrategia: instruir o modelo a preferir formulacao")
    print("      neutra e SINALIZAR quando for impossivel - so essas viram ramo novo.")
    print()
    print("  Custo de inserir um ramo novo: 12 bytes (opcode 0x0002 + expressao de")
    print("  5 palavras) + o texto duplicado. O injetor ja realoca os saltos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
