#!/usr/bin/env python3
"""Confere que o servidor do modelo responde ANTES de disparar as 21.062 falas.

Usa exatamente o mesmo caminho do tradutor: a mesma descoberta de IP do host, o
mesmo endpoint. Se este script passa, o tradutor tambem passa.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import tradutor


def main() -> int:
    print("=" * 72)
    print("TESTE DO SERVIDOR DO MODELO")
    print("=" * 72)
    print(f"  endpoint: {tradutor.SERVIDOR}")

    provas = [
        "Onde fica a espada?",
        "Bem-vindo de volta! Voce esta pronto para forjar?",
    ]
    for texto in provas:
        prompt = (
            "Traduza para portugues do Brasil. Responda SOMENTE com a traducao, "
            f"sem explicacao.\n\n{texto}"
        )
        t0 = time.time()
        r = tradutor.chamar_modelo(prompt, temperatura=0.3)
        dt = time.time() - t0
        if not r:
            print(f"\n  FALHOU: resposta vazia para {texto!r}")
            return 1
        print(f"\n  entrada : {texto}")
        print(f"  saida   : {r.strip()[:200]}")
        print(f"  tempo   : {dt:.1f}s")

    print()
    print("  Servidor respondendo. Pode disparar o tradutor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
