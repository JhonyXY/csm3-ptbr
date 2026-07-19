#!/usr/bin/env python3
"""Mostra as strings de sistema traduzidas, para achar as sem acento.

O menu mostra "Nao" em vez de "Nao com til". Os glifos acentuados estao na ROM
(patch_acentos aplicado), entao ou a string foi traduzida sem acento, ou o
acento se perdeu na hora de codificar.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

OUT = Path(__file__).parent / "_out"

# Palavras que em portugues correto levam acento, escritas sem ele.
SEM_ACENTO = re.compile(
    r"\b(Nao|nao|Sao|sao|Voce|voce|Esta|esta|Ja|ja|Tambem|tambem|"
    r"Ate|ate|Apos|apos|Sim|Entao|entao|Alem|alem|Ninguem|ninguem|"
    r"Alguem|alguem|Porem|porem|Facil|facil|Dificil|dificil|Util|util|"
    r"Magico|magica|Item|Itens|Opcao|opcao|Opcoes|opcoes|Acao|acao|"
    r"Missao|missao|Coracao|coracao|Ferramenta|Municao|municao)\b")


def tem_acento(s: str) -> bool:
    return any(unicodedata.combining(c) or ord(c) > 127
               for c in unicodedata.normalize("NFD", s))


def main() -> int:
    for nome in ("sysstrings.json", "ui_originais.json"):
        caminho = OUT / nome
        if not caminho.exists():
            continue
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        print("=" * 74)
        print(f"{nome}")
        print("=" * 74)

        # Achata para uma lista de (chave, jp, pt)
        itens = []
        if isinstance(dados, dict):
            for chave, v in dados.items():
                if isinstance(v, dict):
                    itens.append((chave, v.get("jp", ""), v.get("pt", "")))
                elif isinstance(v, str):
                    itens.append((chave, "", v))
            if "strings" in dados and isinstance(dados["strings"], list):
                itens = [(e.get("id", "?"), e.get("jp", ""), e.get("pt", ""))
                         for e in dados["strings"]]
        elif isinstance(dados, list):
            itens = [(e.get("id", "?"), e.get("jp", ""), e.get("pt", ""))
                     for e in dados if isinstance(e, dict)]

        print(f"  entradas: {len(itens)}")
        com = [i for i in itens if i[2] and tem_acento(i[2])]
        print(f"  com algum caractere acentuado: {len(com)}")

        suspeitas = [i for i in itens if i[2] and SEM_ACENTO.search(i[2])]
        print(f"  suspeitas de acento faltando : {len(suspeitas)}")
        for chave, jp, pt in suspeitas[:25]:
            achou = SEM_ACENTO.findall(pt)
            print(f"    {str(chave)[:22]:24s} {pt[:44]:46s} <- {achou}")

        if com:
            print("\n  exemplos COM acento (para provar que passa pelo pipeline):")
            for chave, jp, pt in com[:8]:
                print(f"    {str(chave)[:22]:24s} {pt[:50]}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
