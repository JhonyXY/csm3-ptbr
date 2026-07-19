#!/usr/bin/env python3
"""Preenche a traducao das strings de sistema.

Restricao de largura: enquanto o VWF nao entra, cada caractere ocupa 12px fixos
e a caixa de dialogo comporta ~15. As traducoes abaixo respeitam esse teto - por
isso "Sem dinheiro" em vez de "Dinheiro insuficiente".

Sem acentos: a fonte original nao tem vogais acentuadas. Entram quando os 846
glifos livres forem desenhados.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

OUT = Path(__file__).parent / "_out"
LARGURA_MAX = 15

TRADUCAO = {
    "いくつ買いますか？": "Quanto comprar?",
    "いくつ売りますか？": "Quanto vender?",
    "いくつ作りますか？": "Quanto criar?",
    "いくつにしますか？": "Quantos?",
    "売ってもいいですか？": "Confirma venda?",
    "今すぐ装備しますか？": "Equipar agora?",
    "お金が足りません": "Sem dinheiro",
    "材料が足りません": "Sem materiais",
    "これ以上持てません": "Bolsa cheia",
    "売るものが無くなりました": "Estoque vazio",
    "売るものがありません": "Nada a vender",
    "ポイントが足りません": "Sem pontos",
    "アイテムがなくなりました": "Sem itens",
    "武器を持っていません": "Sem armas",
    "回復できません　修理が必要です": "Repare primeiro",
    "装備できません　修理が必要です": "Repare primeiro",
    "アイテム一覧に戻ります": "Voltar a lista",
    "使用しますか？": "Usar?",
    "いくつ捨てますか？": "Quanto jogar?",
    "捨ててもいいですか？": "Confirma?",
    "上書きしますか？": "Sobrescrever?",
    "ロードしますか？": "Carregar?",
    "セーブしますか？": "Salvar?",
    "削除しますか？": "Apagar?",
    "初期化しますか？": "Formatar?",
    "本当によろしいですか？": "Tem certeza?",
    "システムデータを初期化しますか？": "Apagar sistema?",
    "新規データ": "Vazio",
    "データが壊れています": "Dado corrompido",
    "バージョンが違います": "Outra versão",
    "読み込みに失敗しました": "Erro de leitura",
    "書き込みに失敗しました": "Erro ao salvar",
    "電源を切らないでください": "Não desligue",
    "　　　初期化中…": "Formatando...",
    "　　　ロード中…": "Carregando...",
    "セーブ完了しました": "Salvo!",
    "ロード完了しました": "Carregado!",
    "初期化完了しました": "Formatado!",
    "アイテム画面に戻ります": "Voltar a itens",
    "は　い": "Sim",
    "いいえ": "Não",
}


def main() -> int:
    path = OUT / "sysstrings.json"
    d = json.loads(path.read_text(encoding="utf-8"))

    traduzidas = 0
    faltando = []
    largas = []

    for e in d["strings"]:
        pt = TRADUCAO.get(e["jp"])
        if pt is None:
            faltando.append(e["jp"])
            continue
        e["pt"] = pt
        traduzidas += 1
        if len(pt) > LARGURA_MAX:
            largas.append((e["jp"], pt, len(pt)))

    path.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=" * 72)
    print("TRADUCAO DAS STRINGS DE SISTEMA")
    print("=" * 72)
    print(f"  entradas traduzidas: {traduzidas} de {len(d['strings'])}")
    if faltando:
        print(f"  sem traducao       : {len(faltando)}")
        for jp in faltando[:8]:
            print(f"      \"{jp}\"")

    if largas:
        print()
        print(f"  ACIMA DE {LARGURA_MAX} CARACTERES (vao vazar da caixa sem VWF):")
        for jp, pt, n in largas:
            px = n * 12
            print(f"      \"{pt}\" = {n}ch = {px}px   (era \"{jp}\")")
        print()
        print("  Com o VWF ativo (~7,35px/char) essas caberiam:")
        for jp, pt, n in largas:
            print(f"      \"{pt}\" -> {n*7.35:.0f}px")

    print()
    print("  --- amostra do que voce vai ver no menu de save ---")
    for e in d["strings"]:
        if e["jp"] in ("セーブしますか？", "は　い", "いいえ"):
            print(f"      \"{e['jp']}\"  ->  \"{e['pt']}\"")

    print(f"\n  gravado: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
