#!/usr/bin/env python3
"""Monta o JSON de traducao do teste de ponta a ponta.

Pega as strings do script 8 (menu inicial) e aplica um dicionario de traducao
feito a mao. Sem acentos: a fonte original so tem o alfabeto latino basico -
acentuadas entram quando os 846 glifos livres forem preenchidos.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

OUT = Path(__file__).parent / "_out"

TRADUCOES = {
    "本編": "Historia",
    "自由行動": "Acao Livre",
    "サウンドテスト": "Sons",
    "おまけ": "Extras",
    "通信": "Link",
    "０話": "Cap 0",
    "１話": "Cap 1",
    "２話": "Cap 2",
    "３話": "Cap 3",
    "４話": "Cap 4",
    "５話": "Cap 5",
    "６話": "Cap 6",
    "７話": "Cap 7",
    "８話": "Cap 8",
    "９話": "Cap 9",
    "１０話": "Cap 10",
    "１１話": "Cap 11",
    "１２話": "Cap 12",
    "最終話": "Final",
    "エンディング": "Finais",
    "次へ": "Mais",
    "戻る": "Voltar",
    "はい": "Sim",
    "いいえ": "Nao",
    "つづきから": "Continuar",
    "はじめから": "Novo Jogo",
    "セーブ": "Salvar",
    "ロード": "Carregar",
    "もどる": "Voltar",
    "やめる": "Sair",
}


def main() -> int:
    src = OUT / "textos_originais.json"
    d = json.loads(src.read_text(encoding="utf-8"))

    alvo_scripts = {8}
    escolhidas = []
    usados = set()

    for e in d["strings"]:
        if e["script"] not in alvo_scripts:
            continue
        pt = TRADUCOES.get(e["jp"])
        if pt:
            novo = dict(e)
            novo["pt"] = pt
            escolhidas.append(novo)
            usados.add(e["jp"])

    print("=" * 72)
    print("STRINGS DO SCRIPT 8 (menu inicial)")
    print("=" * 72)
    todas = [e for e in d["strings"] if e["script"] in alvo_scripts]
    for e in todas:
        pt = TRADUCOES.get(e["jp"], "")
        marca = "  ->  " + pt if pt else "      (nao traduzida)"
        print(f"  @0x{e['offset']:04X} {e['opcode']}  {e['jp']:<12}{marca}")

    print()
    print(f"  total no script : {len(todas)}")
    print(f"  traduzidas      : {len(escolhidas)}")
    nao_usadas = set(TRADUCOES) - usados
    if nao_usadas:
        print(f"  do dicionario sem correspondencia: {', '.join(sorted(nao_usadas))}")

    out = OUT / "traducao_teste.json"
    out.write_text(
        json.dumps({"_meta": {"teste": "menu inicial"}, "strings": escolhidas},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  gravado: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
