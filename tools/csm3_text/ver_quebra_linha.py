#!/usr/bin/env python3
"""Como o original marca quebra de linha dentro de uma caixa?

O texto traduzido passa reto da borda da caixa, enquanto as tres linhas de
baixo ficam vazias. Ou o jogo quebra sozinho (e algo no meu texto impede), ou o
japones traz uma marca explicita que a traducao perdeu.

Procura a marca comparando falas japonesas CURTAS com LONGAS: se as longas
tiverem algo que as curtas nao tem, e isso.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).parent / "_out"


def main() -> int:
    dados = json.loads((OUT / "falas_originais.json").read_text(encoding="utf-8"))
    falas = dados["falas"] + dados.get("itens", [])

    print("=" * 74)
    print("O JAPONES TEM QUEBRA EXPLICITA?")
    print("=" * 74)

    com_n = [e for e in falas if "\n" in e.get("jp", "")]
    print(f"  falas com '\\n' no texto : {len(com_n):,} de {len(falas):,}")

    # O campo 'linhas' que o extrator gravou
    linhas_dist = Counter(e.get("linhas") for e in falas)
    print(f"  campo 'linhas'          : {dict(sorted(linhas_dist.items(), key=lambda x: (x[0] is None, x[0])))}")

    # Caracteres nao imprimiveis ou de controle no meio do texto
    especiais = Counter()
    for e in falas:
        for ch in e.get("jp", ""):
            if ord(ch) < 0x20 or 0x7F <= ord(ch) < 0xA0:
                especiais[f"U+{ord(ch):04X}"] += 1
    print(f"  caracteres de controle  : {dict(especiais)}")

    print()
    print("=" * 74)
    print("ESTRUTURA DE UMA FALA LONGA (a que estourou a caixa)")
    print("=" * 74)
    longas = sorted(falas, key=lambda e: -len(e.get("jp", "")))
    for e in longas[:3]:
        print()
        print(f"  script {e['script']} offset 0x{e['offset']:05X} "
              f"({len(e['jp'])} caracteres, linhas={e.get('linhas')})")
        print(f"    jp: {e['jp'][:90]}")
        for bloco in e.get("estrutura", []):
            print(f"    bloco: offset 0x{bloco['offset']:05X} "
                  f"opcode {bloco['opcode']} pad {bloco.get('pad')} "
                  f"chars {bloco.get('chars')}")

    print()
    print("=" * 74)
    print("A FALA QUE VOCE VIU ESTOURAR")
    print("=" * 74)
    alvo = "強くなったねぇ"
    for e in falas:
        if alvo in e.get("jp", ""):
            print(f"  script {e['script']} offset 0x{e['offset']:05X}")
            print(f"    jp    : {e['jp']}")
            print(f"    linhas: {e.get('linhas')}")
            print(f"    chars : {e.get('chars')}")
            for bloco in e.get("estrutura", []):
                print(f"    bloco : offset 0x{bloco['offset']:05X} "
                      f"opcode {bloco['opcode']} pad {bloco.get('pad')} "
                      f"chars {bloco.get('chars')}")
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
