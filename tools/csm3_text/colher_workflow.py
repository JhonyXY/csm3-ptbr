#!/usr/bin/env python3
"""Colhe os achados dos agentes que ja terminaram, do journal do workflow.

O workflow foi cortado no meio, mas 125 agentes ja tinham devolvido resultado.
Jogar isso fora seria desperdicio - este script extrai so o que interessa
(achados marcados como relevantes, e os veredictos dos ceticos), deduplicado
por arquivo:linha.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

JOURNAL = Path("/mnt/c/Users/Jhony/.claude/projects/"
               "c--Users-Jhony-Downloads-decomps-Summon-Knight/"
               "398a0107-b922-4df8-bd3d-cb1deab6e71a/subagents/workflows/"
               "wf_1f092ab4-bb4/journal.jsonl")


def desembrulhar(v):
    """O resultado pode vir como dict, ou como string JSON dentro de um campo."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return None
    return v


def main() -> int:
    if not JOURNAL.exists():
        print(f"  nao achei: {JOURNAL}")
        return 1

    achados = []
    veredictos = []
    outros = 0

    for linha in JOURNAL.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            reg = json.loads(linha)
        except Exception:
            continue
        if reg.get("type") != "result":
            continue
        val = reg.get("value")
        if val is None:
            val = reg.get("result")
        val = desembrulhar(val)
        if not isinstance(val, dict):
            outros += 1
            continue
        if "achados" in val:
            for a in val["achados"]:
                if isinstance(a, dict):
                    achados.append(a)
        elif "refutado" in val:
            veredictos.append(val)
        else:
            outros += 1

    print("=" * 78)
    print("COLHEITA DO WORKFLOW INTERROMPIDO")
    print("=" * 78)
    print(f"  achados brutos : {len(achados)}")
    print(f"  veredictos     : {len(veredictos)}")
    print(f"  outros results : {outros}")

    # Dedup por arquivo:linha, guardando a melhor confianca.
    ordem = {"alta": 3, "media": 2, "baixa": 1}
    por_local = {}
    for a in achados:
        chave = f"{a.get('arquivo')}:{a.get('linha')}"
        atual = por_local.get(chave)
        if atual is None or ordem.get(a.get("confianca"), 0) > ordem.get(
                atual.get("confianca"), 0):
            por_local[chave] = a

    relevantes = [a for a in por_local.values() if a.get("relevante")]
    print(f"  locais unicos  : {len(por_local)}")
    print(f"  relevantes     : {len(relevantes)}")

    print()
    print("=" * 78)
    print("ACHADOS RELEVANTES (deduplicados por local)")
    print("=" * 78)
    for a in sorted(relevantes, key=lambda x: (str(x.get("arquivo")),
                                               x.get("linha") or 0)):
        print()
        print(f"  {a.get('arquivo')}:{a.get('linha')}  [{a.get('confianca')}]")
        print(f"    funcao: {a.get('funcao')}")
        print(f"    {a.get('titulo')}")
        ev = str(a.get("evidencia", "")).replace("\n", "\n      ")
        print(f"      {ev[:700]}")
        if a.get("implicacao"):
            print(f"    -> {str(a['implicacao'])[:400]}")

    # Os veredictos nao carregam de volta o achado; conta o placar geral.
    if veredictos:
        refutados = sum(1 for v in veredictos if v.get("refutado"))
        print()
        print("=" * 78)
        print(f"CETICOS: {refutados} de {len(veredictos)} votaram REFUTADO")
        print("=" * 78)
        for v in veredictos[:14]:
            marca = "REFUTA " if v.get("refutado") else "sustenta"
            print(f"\n  [{marca}] {str(v.get('razao', ''))[:320]}")
            if v.get("o_que_de_fato_acontece"):
                print(f"      real: {str(v['o_que_de_fato_acontece'])[:320]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
