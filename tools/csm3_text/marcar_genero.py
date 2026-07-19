#!/usr/bin/env python3
"""Marca cada fala com o ramo de genero em que ela vive.

O jogo bifurca o dialogo pela variavel 0x182 (0 = masculino). Uma fala dentro do
ramo masculino so aparece para quem escolheu Ritchburn; a do ramo feminino, so
para quem escolheu Rifmonica. As demais aparecem para os dois.

Sem essa marcacao o modelo escreve "fiquei surpreso" em fala que a protagonista
tambem diz - errado para metade dos jogadores.

Acrescenta o campo "genero" a falas_originais.json:
    "M"        so aparece para o protagonista masculino
    "F"        so para a feminina
    "ambos"    compartilhada - a traducao precisa evitar flexao
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

VAR_GENERO = 0x0182
TOKEN_VAR = 0x0002
OPCODE_SALTO_COND = 0x0002


def expressao_le_genero(words: list[int]) -> bool:
    i = 0
    while i < len(words):
        tok = words[i]
        if tok == 0:
            break
        if tok in (0x0001, 0x0002, 0x0003):
            if tok == TOKEN_VAR and i + 1 < len(words) and words[i + 1] == VAR_GENERO:
                return True
            i += 2
        else:
            i += 1
    return False


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    auto_map = walker.load_auto_map()

    # offset -> genero, por script
    marcas: dict[int, dict[int, str]] = {}

    for script in csm3rom.iter_scripts(rom):
        body = bytes(script.body)
        result = walker.walk(body, auto_map)
        faixas = []
        # Indexa por offset para achar a instrucao que fecha o bloco masculino.
        por_offset_ins = {i.offset: i for i in result.instructions}

        for ins in result.instructions:
            if ins.opcode != OPCODE_SALTO_COND:
                continue
            alvo = expr = None
            for kind, palavras in ins.parts:
                if kind == "word" and alvo is None:
                    alvo = palavras[0] & ~1
                elif kind == "expr":
                    expr = palavras
            if alvo is None or expr is None:
                continue
            fim = ins.offset + ins.size
            if alvo <= fim or not expressao_le_genero(expr):
                continue
            # A expressao e "genero == 0", que vale 1 para masculino. O opcode
            # SALTA quando a expressao da zero, entao masculino cai no
            # fall-through: [fim, alvo) e o texto MASCULINO.
            faixas.append((fim, alvo, "M"))

            # O bloco masculino costuma terminar com um salto incondicional
            # (0x0003) para depois do bloco feminino. Se for o caso, o feminino
            # vai de `alvo` ate esse destino.
            anteriores = [o for o in por_offset_ins if fim <= o < alvo]
            if not anteriores:
                continue
            ultimo = por_offset_ins[max(anteriores)]
            if ultimo.opcode != 0x0003:
                continue
            palavras = [w[0] for kind, w in ultimo.parts if kind == "word"]
            if not palavras:
                continue
            fim_feminino = palavras[0] & ~1
            if alvo < fim_feminino:
                faixas.append((alvo, fim_feminino, "F"))

        por_offset = {}
        for ins in result.instructions:
            if not ins.is_text:
                continue
            g = "ambos"
            for a, b, marca in faixas:
                if a <= ins.offset < b:
                    g = marca
                    break
            por_offset[ins.offset] = g
        marcas[script.index] = por_offset

    # Aplica no arquivo de falas.
    caminho = OUT / "falas_originais.json"
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    contagem = Counter()

    for u in dados["falas"] + dados["itens"]:
        g = marcas.get(u["script"], {}).get(u["offset"], "ambos")
        u["genero"] = g
        contagem[g] += 1

    caminho.write_text(json.dumps(dados, indent=2, ensure_ascii=False),
                       encoding="utf-8")

    print("=" * 72)
    print("MARCACAO DE GENERO APLICADA")
    print("=" * 72)
    total = sum(contagem.values())
    for g in ("M", "F", "ambos"):
        n = contagem[g]
        rotulo = {"M": "so protagonista masculino",
                  "F": "so protagonista feminina",
                  "ambos": "compartilhada"}[g]
        print(f"  {g:6s} {n:6,d} ({100*n/total:4.1f}%)  {rotulo}")

    print()
    print("  As marcadas M/F podem usar flexao a vontade - o jogo so as mostra")
    print("  para o genero certo. As 'ambos' precisam de formulacao neutra.")
    print(f"\n  gravado: {caminho.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
