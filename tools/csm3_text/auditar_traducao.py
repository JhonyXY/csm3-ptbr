#!/usr/bin/env python3
"""Auditoria de qualidade do piloto: procura problemas concretos.

O agregado (expansao, overflow) nao diz se a traducao presta. Este script caca
os defeitos que importam num RPG:

  CONCORDANCIA  o protagonista pode ser homem OU mulher (o jogador escolhe).
                Adjetivo flexionado referindo-se a ele erra para metade dos
                jogadores. E o defeito mais grave e o mais facil de passar
                despercebido.
  REDUNDANCIA   "iam ir", "vou ir" - portugues ruim que o modelo produz ao
                traduzir literalmente formas japonesas.
  GLOSSARIO     nome fora da grafia fixada.
  RETICENCIAS   o japones usa … demais; em portugues cansa.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

OUT = Path(__file__).parent / "_out"

# Adjetivos e participios que flexionam e costumam referir-se ao protagonista.
# So flagra quando o adjetivo vem depois de copula referindo-se a quem fala.
# "que surpresa" e substantivo; "fiquei surpreso" e que erra o genero.
FLEXIONADOS = re.compile(
    r"\b(?:fiquei|fico|estou|to|tô|sou|era|fui|me sinto|tava|estava|"
    r"ficaria|seria|continuo|ando)\s+(?:meio\s+|muito\s+|bem\s+|tão\s+|"
    r"um pouco\s+)?"
    r"(surpres[oa]|cansad[oa]|preocupad[oa]|assustad[oa]|sozinh[oa]|"
    r"perdid[oa]|prepara?d[oa]|obrigad[oa]|pront[oa]|segur[oa]|nervos[oa]|"
    r"animad[oa]|chatead[oa]|confus[oa]|salv[oa]|escolhid[oa]|machucad[oa])\b",
    re.IGNORECASE,
)
REDUNDANTE = re.compile(r"\b(iam?\s+ir|vou\s+ir|vai\s+ir|ir\s+embora\s+daqui)\b",
                        re.IGNORECASE)


def main() -> int:
    arquivo = sys.argv[1] if len(sys.argv) > 1 else "p78.json"
    d = json.loads((OUT / arquivo).read_text(encoding="utf-8"))
    trads = [t for t in d["traducoes"] if t.get("pt")]

    glossario = {}
    gp = OUT / "glossario_final.json"
    if gp.exists():
        g = json.loads(gp.read_text(encoding="utf-8"))
        for secao in ("confirmados", "revisar"):
            for e in g.get(secao, []):
                if e.get("pt"):
                    glossario[e["jp"]] = e["pt"]

    print("=" * 74)
    print(f"AUDITORIA - {len(trads)} traducoes de {arquivo}")
    print("=" * 74)

    # De qual ramo cada fala veio? Flexao so e problema em fala COMPARTILHADA -
    # nas de ramo M/F o jogo so mostra para o genero certo.
    ramo = {}
    fp = OUT / "falas_originais.json"
    if fp.exists():
        f = json.loads(fp.read_text(encoding="utf-8"))
        for u in f["falas"] + f["itens"]:
            ramo[u["jp"]] = u.get("genero", "ambos")

    genero, redundancia, glos, reticencias = [], [], [], []
    flex_ok = 0

    for t in trads:
        pt, jp = t["pt"], t["jp"]
        m = FLEXIONADOS.search(pt)
        if m:
            if ramo.get(jp, "ambos") in ("M", "F"):
                flex_ok += 1          # flexao legitima: ramo exclusivo
            else:
                genero.append((t, m.group(0)))
        if REDUNDANTE.search(pt):
            redundancia.append(t)
        for jp_termo, pt_termo in glossario.items():
            if jp_termo in jp and pt_termo not in pt:
                glos.append((t, jp_termo, pt_termo))
        if pt.count("...") + pt.count("…") >= 2:
            reticencias.append(t)

    print(f"\n  1. CONCORDANCIA DE GENERO")
    print(f"     flexao em fala COMPARTILHADA (problema): {len(genero)} de {len(trads)}"
          f" ({100*len(genero)/len(trads):.0f}%)")
    print(f"     flexao em fala de ramo exclusivo (ok)   : {flex_ok}")
    print("     So a primeira e defeito - a segunda o jogo so mostra para o")
    print("     genero certo.")
    for t, palavra in genero[:6]:
        print(f"       \"{palavra}\" em: {t['pt']}")

    print(f"\n  2. REDUNDANCIA: {len(redundancia)}")
    for t in redundancia[:5]:
        print(f"       {t['pt']}")

    print(f"\n  3. GLOSSARIO IGNORADO: {len(glos)}")
    for t, jp_t, pt_t in glos[:5]:
        print(f"       esperava '{pt_t}' (de {jp_t}): {t['pt']}")

    print(f"\n  4. EXCESSO DE RETICENCIAS: {len(reticencias)}")
    for t in reticencias[:3]:
        print(f"       {t['pt']}")

    print()
    print("=" * 74)
    print("AMOSTRA COMPLETA")
    print("=" * 74)
    for t in trads[:18]:
        print(f"\n  jp: {t['jp']}")
        print(f"  pt: {t['pt']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
