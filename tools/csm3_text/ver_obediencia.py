#!/usr/bin/env python3
"""O modelo obedece o limite de caracteres que eu mando no prompt?

Depois de trocar o orcamento para "25 caracteres por linha de tela", o numero
de falas que nao cabem quase nao mudou. Ou o limite nao esta chegando certo no
prompt, ou o modelo o ignora. Este script compara, fala a fala, o limite pedido
com o tamanho entregue.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = Path(__file__).parent / "_out"
POR_LINHA = 25


def main() -> int:
    script_alvo = int(sys.argv[1]) if len(sys.argv) > 1 else 1603

    originais = json.loads(
        (OUT / "falas_originais.json").read_text(encoding="utf-8"))
    info = {}
    for e in originais["falas"] + originais.get("itens", []):
        if e.get("script") == script_alvo:
            linhas = len(e.get("estrutura") or []) or e.get("linhas") or 1
            info[e["id"]] = (linhas, e.get("jp", ""))

    trad = json.loads((OUT / "traducao.json").read_text(encoding="utf-8"))

    linhas_dist = {}
    passou = coube = 0
    exemplos = []
    for t in trad["traducoes"]:
        dados = info.get(t.get("id"))
        if dados is None:
            continue
        n_linhas, jp = dados
        pt = (t.get("pt") or "").strip()
        if not pt:
            continue
        limite = max(20, min(54, n_linhas * POR_LINHA))
        linhas_dist[n_linhas] = linhas_dist.get(n_linhas, 0) + 1
        if len(pt) > limite:
            passou += 1
            if len(exemplos) < 8:
                exemplos.append((n_linhas, limite, len(pt), pt))
        else:
            coube += 1

    total = passou + coube
    print("=" * 74)
    print(f"OBEDIENCIA AO LIMITE - script {script_alvo}")
    print("=" * 74)
    print(f"  falas conferidas      : {total}")
    print(f"  dentro do limite      : {coube}  ({100*coube/total:.0f}%)")
    print(f"  PASSARAM do limite    : {passou}  ({100*passou/total:.0f}%)")
    print(f"  distribuicao de linhas: {dict(sorted(linhas_dist.items()))}")
    print()
    print("  exemplos que passaram:")
    for n, lim, tam, pt in exemplos:
        print(f"    {n} linha(s), limite {lim}, entregue {tam}:")
        print(f"      {pt[:72]}")
    print()
    if passou > total * 0.3:
        print("  O modelo NAO esta respeitando o limite. Instrucao no prompt")
        print("  nao basta - precisa de validacao com retentativa, como ja e")
        print("  feito para a flexao de genero.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
