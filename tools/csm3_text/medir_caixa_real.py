#!/usr/bin/env python3
"""Qual a largura REAL de uma linha, medida no proprio jogo?

Em vez de eu supor 240px (a tela), mede as linhas JAPONESAS originais: cada
caractere ocupa 12px fixos, entao a linha mais larga que o jogo usa E o
orcamento de verdade. E dai sai quantos caracteres em portugues cabem, usando a
media do VWF.

Mede tambem quantas linhas cada caixa tem, que e o que permitiria redistribuir
o texto em vez de espremer cada linha isolada.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).parent / "_out"
PX_POR_CHAR_JP = 12


def main() -> int:
    dados = json.loads((OUT / "falas_originais.json").read_text(encoding="utf-8"))
    falas = dados["falas"] + dados.get("itens", [])

    larguras = []
    for e in falas:
        jp = e.get("jp", "")
        if not jp.strip():
            continue
        # Os placeholders {g} viram 1 caractere na tela, nao 3.
        n = len(jp)
        for tag in ("{g}", "{d}", "{z}", "{b}", "{e}", "{t}"):
            n -= jp.count(tag) * 2
        larguras.append(n * PX_POR_CHAR_JP)

    larguras.sort()
    total = len(larguras)

    def pct(p):
        return larguras[min(total - 1, int(total * p / 100))]

    print("=" * 74)
    print("LARGURA DAS LINHAS JAPONESAS ORIGINAIS")
    print("=" * 74)
    print(f"  linhas          : {total:,}")
    print(f"  media           : {sum(larguras)/total:.0f}px")
    print(f"  mediana         : {pct(50)}px")
    print(f"  percentil 90    : {pct(90)}px")
    print(f"  percentil 99    : {pct(99)}px")
    print(f"  MAIOR           : {larguras[-1]}px  <- o orcamento real da linha")

    teto = larguras[-1]
    print()
    print("=" * 74)
    print("QUANTOS CARACTERES EM PORTUGUES CABEM NISSO")
    print("=" * 74)
    for folga, avanco in ((0, 7.35), (1, 8.34), (2, 9.32)):
        print(f"  folga {folga}px  ->  {avanco}px por letra  ->  "
              f"{int(teto / avanco)} caracteres por linha")

    print()
    print("=" * 74)
    print("QUANTAS LINHAS TEM UMA CAIXA")
    print("=" * 74)
    print("  (linhas consecutivas no mesmo script, agrupadas por proximidade)")

    # Agrupa por script e por offsets proximos: linhas da mesma caixa ficam a
    # poucas dezenas de bytes uma da outra.
    por_script = {}
    for e in falas:
        if e.get("script") is None:
            continue
        por_script.setdefault(e["script"], []).append(e)

    tamanhos = Counter()
    for script, lista in por_script.items():
        lista.sort(key=lambda x: x["offset"])
        grupo = 1
        for a, b in zip(lista, lista[1:]):
            if b["offset"] - a["offset"] <= 80:
                grupo += 1
            else:
                tamanhos[grupo] += 1
                grupo = 1
        tamanhos[grupo] += 1

    caixas = sum(tamanhos.values())
    for n in sorted(tamanhos):
        if tamanhos[n] < caixas * 0.01:
            continue
        barra = "#" * int(40 * tamanhos[n] / max(tamanhos.values()))
        print(f"    {n:2d} linha(s): {tamanhos[n]:6,d}  {barra}")
    print(f"\n  caixas estimadas: {caixas:,}")
    print(f"  media de linhas por caixa: "
          f"{sum(n*c for n, c in tamanhos.items())/caixas:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
