#!/usr/bin/env python3
"""Por que 25% das falas voltam vazias? Testa a hipotese da posicao no lote.

25% de 12 e exatamente 3. Se as vazias forem sempre as ULTIMAS do lote, a causa
e a resposta do modelo sendo cortada - ele traduz as primeiras e para. Se
estiverem espalhadas, e outra coisa (conteudo, formato da linha, refusa).

Este script responde isso de duas formas independentes:
  1. olhando o que ja foi gravado, pela posicao de cada falha no lote
  2. mandando um lote de verdade e contando quantas linhas voltam
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import tradutor

OUT = Path(__file__).parent / "_out"
LOTE = 12


def parte1() -> None:
    caminho = OUT / "traducao.json"
    if not caminho.exists():
        print("  sem traducao.json ainda")
        return
    trad = json.loads(caminho.read_text(encoding="utf-8"))["traducoes"]

    print("=" * 72)
    print("1. POSICAO DA FALHA DENTRO DO LOTE")
    print("=" * 72)
    print(f"  (lote = {LOTE}; se as falhas se concentrarem no fim, e corte)")
    print()

    pos_falha = Counter()
    pos_total = Counter()
    for i, e in enumerate(trad):
        p = i % LOTE + 1
        pos_total[p] += 1
        if e.get("erro") or not e.get("pt"):
            pos_falha[p] += 1

    for p in range(1, LOTE + 1):
        t, f = pos_total[p], pos_falha[p]
        pct = 100 * f / t if t else 0
        barra = "#" * int(pct / 5)
        print(f"    posicao {p:2d}: {f:3d}/{t:3d}  {pct:5.1f}%  {barra}")

    fim = sum(pos_falha[p] for p in range(LOTE - 2, LOTE + 1))
    total = sum(pos_falha.values())
    if total:
        print()
        print(f"  nas 3 ultimas posicoes: {fim} de {total} falhas "
              f"({100*fim/total:.0f}%)")
        if fim / total > 0.7:
            print("  => CORTE. O modelo para antes de terminar o lote.")
        else:
            print("  => espalhado. Nao e corte; a causa e outra.")


def parte2() -> None:
    print()
    print("=" * 72)
    print("2. TESTE AO VIVO: um lote de 12, quantas linhas voltam?")
    print("=" * 72)

    dados = json.loads((OUT / "falas_originais.json").read_text(encoding="utf-8"))
    todas = [u for u in dados["falas"] + dados["itens"] if u["jp"].strip()]
    lote = todas[:LOTE]
    for u in lote:
        u["_jp_mascarado"], u["_reverso"] = tradutor.mascarar(u["jp"])
        u["_limite"] = 78

    glossario = tradutor.carregar_glossario()
    prompt = tradutor.montar_prompt(lote, glossario)
    print(f"  prompt: {len(prompt):,} chars (~{len(prompt)//3:,} tokens)")

    resposta = tradutor.chamar_modelo(prompt, temperatura=0.3)
    if resposta is None:
        print("  servidor nao respondeu")
        return

    print(f"  resposta: {len(resposta):,} chars")
    numeradas = re.findall(r"^\s*(\d+)\s*[:.)\-]", resposta, re.M)
    print(f"  linhas numeradas devolvidas: {len(numeradas)} de {LOTE}")
    print(f"  numeros vistos: {sorted(set(int(n) for n in numeradas))}")

    parseado = tradutor.parsear(resposta, LOTE)
    faltando = [i for i in range(1, LOTE + 1) if i not in parseado]
    print(f"  faltando apos o parse: {faltando}")

    print()
    print("  --- ultimos 400 chars da resposta crua ---")
    print("  " + resposta[-400:].replace("\n", "\n  "))

    if faltando and max(numeradas or ["0"], key=int) and faltando == list(
            range(min(faltando), LOTE + 1)):
        print()
        print("  => A resposta acaba no meio. Confirma o corte.")


if __name__ == "__main__":
    parte1()
    parte2()
