#!/usr/bin/env python3
"""Localiza, em data/*.s, os blocos .incbin que contem as strings de sistema.

Para migrar a traducao para o build, cada string precisa virar dado de verdade
com rotulo proprio. Isso exige quebrar o .incbin que hoje a engloba.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"

INCBIN = re.compile(r'^\s*\.incbin\s+"baserom\.gba",\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+)')
LABEL = re.compile(r"^(\w+)::")


def indexar() -> list[dict]:
    """Lista todos os blocos incbin de data/*.s com arquivo, linha e faixa."""
    blocos = []
    for path in sorted((REPO / "data").glob("*.s")):
        label = None
        for i, linha in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            m = LABEL.match(linha)
            if m:
                label = m.group(1)
                continue
            m = INCBIN.match(linha)
            if m:
                off = int(m.group(1), 16)
                size = int(m.group(2), 16)
                blocos.append({
                    "arquivo": path.name,
                    "linha": i,
                    "rotulo": label,
                    "off": off,
                    "size": size,
                    "fim": off + size,
                })
    return blocos


def main() -> int:
    dados = json.loads((OUT / "sysstrings.json").read_text(encoding="utf-8"))
    alvos = sorted({e["alvo"] for e in dados["strings"]})

    blocos = indexar()
    print("=" * 72)
    print("BLOCOS QUE CONTEM AS STRINGS DE SISTEMA")
    print("=" * 72)
    print(f"  blocos incbin em data/: {len(blocos):,}")
    print(f"  strings distintas     : {len(alvos)}")
    print()

    por_bloco: dict[tuple, list[int]] = {}
    orfas = []
    for alvo in alvos:
        achou = None
        for b in blocos:
            if b["off"] <= alvo < b["fim"]:
                achou = b
                break
        if achou is None:
            orfas.append(alvo)
            continue
        chave = (achou["arquivo"], achou["linha"], achou["rotulo"],
                 achou["off"], achou["size"])
        por_bloco.setdefault(chave, []).append(alvo)

    for (arq, linha, rotulo, off, size), lista in sorted(por_bloco.items()):
        print(f"  {arq}:{linha}  {rotulo}")
        print(f"      faixa 0x{off:07X}..0x{off+size:07X} ({size:,} bytes)  "
              f"contem {len(lista)} string(s)")
        for a in lista[:4]:
            print(f"          0x{a:07X} (+{a-off} dentro do bloco)")
        if len(lista) > 4:
            print(f"          ... e mais {len(lista)-4}")

    print()
    print(f"  blocos distintos a quebrar: {len(por_bloco)}")
    if orfas:
        print(f"  strings fora de qualquer bloco: {len(orfas)}")

    # Ponteiros: cada um ja e um bloco de 4 bytes proprio?
    print()
    print("=" * 72)
    print("OS PONTEIROS JA ESTAO ISOLADOS?")
    print("=" * 72)
    isolados = 0
    nao = []
    for e in dados["strings"]:
        p = e["ponteiro"]
        for b in blocos:
            if b["off"] == p and b["size"] == 4:
                isolados += 1
                break
        else:
            nao.append(p)
    print(f"  ponteiros com bloco proprio de 4 bytes: {isolados} de {len(dados['strings'])}")
    if nao:
        print(f"  precisam ser separados: {len(nao)}")
        for p in nao[:6]:
            print(f"      0x{p:07X}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
