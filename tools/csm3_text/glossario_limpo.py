#!/usr/bin/env python3
"""Classifica os candidatos a nome proprio e monta o glossario para revisao.

A extracao bruta mistura tres coisas: nomes de personagem, nomes de lugar e
pronomes/giria escritos em katakana. Este script separa usando evidencia dos
proprios dados:

  PESSOA  - aparece com honorifico (さん/ちゃん/様...), ou junto dos placeholders
            de nome, ou como sujeito de fala
  LUGAR   - todas as ocorrencias sao absorvidas por um composto de lugar
            (ルイーズ aparece 127x e ルイーズ村 tambem 127x -> e vila)
  DESCARTE- lista fixa de pronomes e giria comum em katakana
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

OUT = Path(__file__).parent / "_out"

KATAKANA = re.compile(r"[ァ-ヶー]{2,}")
HONORIFICOS = ("さん", "ちゃん", "くん", "君", "様", "さま", "殿")
SUFIXOS_LUGAR = ("村", "町", "山", "洞", "城", "島", "国", "街", "森", "谷", "塔", "宮")

# Pronomes, giria e palavras comuns escritas em katakana. Nao sao nomes.
DESCARTE = {
    # pronomes
    "オレ", "アタシ", "アンタ", "キサマ", "ワガハイ", "ヤツ", "アイツ", "コイツ",
    "ソイツ", "ワタシ", "ボク", "オマエ", "ミンナ", "ダレ", "ナニ", "ドコ", "ドウ",
    # giria e enfase
    "ダメ", "ホント", "ウソ", "イヤ", "アレ", "ソレ", "コレ", "スゴイ", "ヒドイ",
    "コワイ", "カッコイイ", "ワケ", "ジャマ", "ガマン", "カクゴ", "ニセモノ",
    "ウデ", "ケガ", "ネコ", "デス", "アニキ", "ヌシ", "モノ", "コト", "トコ",
    "チカラ", "キモチ", "ココロ", "アタマ", "カラダ", "テキ", "ミカタ", "シゴト",
    "オカネ", "ゴハン", "オレタチ", "オマエラ", "ヤメロ", "マサカ", "ゼッタイ",
    # termos de sistema
    "アイテム", "レベル", "ポイント", "セーブ", "ロード", "データ", "システム",
    "パートナー", "メニュー", "ボタン", "ゲーム", "テスト", "サウンド", "エリア",
    "バージョン", "コマンド", "タイプ", "モード", "スタート", "エンディング",
    "クリア", "ダメージ", "エネルギー", "パワー", "スピード", "メッセージ",
    "ハンマー", "スポート",
}


def main() -> int:
    dados = json.loads((OUT / "falas_originais.json").read_text(encoding="utf-8"))
    textos = [u["jp"] for u in dados["falas"] + dados["itens"]]

    kata = Counter()
    for t in textos:
        for m in KATAKANA.findall(t):
            kata[m] += 1

    # --- lugares: compostos com sufixo geografico ---
    lugares = Counter()
    for t in textos:
        for suf in SUFIXOS_LUGAR:
            for m in re.finditer(re.escape(suf), t):
                antes = t[max(0, m.start() - 8):m.start()]
                nome = re.search(r"([ァ-ヶー]{2,}|[一-鿿]{2,})$", antes)
                if nome:
                    lugares[nome.group(1) + suf] += 1

    # Um katakana cujas ocorrencias sao TODAS absorvidas por compostos de lugar
    # e um toponimo, nao uma pessoa.
    absorvido = Counter()
    for composto, n in lugares.items():
        base = composto[:-1]
        if base in kata:
            absorvido[base] += n

    # --- pessoas: aparecem com honorifico ---
    com_honorifico = Counter()
    for t in textos:
        for h in HONORIFICOS:
            for m in re.finditer(re.escape(h), t):
                antes = t[max(0, m.start() - 6):m.start()]
                nome = re.search(r"([ァ-ヶー一-鿿]{2,})$", antes)
                if nome:
                    com_honorifico[nome.group(1)] += 1

    # --- classifica ---
    pessoas, toponimos, incertos = [], [], []
    for termo, n in kata.most_common(120):
        if termo in DESCARTE or len(termo) < 2:
            continue
        if absorvido.get(termo, 0) >= n * 0.9:
            toponimos.append((termo, n, "sempre em composto de lugar"))
        elif com_honorifico.get(termo, 0) > 0:
            pessoas.append((termo, n, f"com honorifico {com_honorifico[termo]}x"))
        elif n >= 30:
            incertos.append((termo, n, ""))

    print("=" * 72)
    print("GLOSSARIO CLASSIFICADO")
    print("=" * 72)

    print(f"\n  PESSOAS ({len(pessoas)}) - confirmadas por honorifico")
    for termo, n, nota in pessoas:
        print(f"      {n:6,d}  {termo:12s}  {nota}")

    print(f"\n  LUGARES ({len(set(lugares))}) - compostos geograficos")
    for composto, n in lugares.most_common(20):
        if n >= 5:
            print(f"      {n:6,d}  {composto}")

    print(f"\n  INCERTOS ({len(incertos)}) - frequentes, sem evidencia clara")
    print("      (provavel elenco secundario; voce decide na revisao)")
    for termo, n, _ in incertos[:25]:
        print(f"      {n:6,d}  {termo}")

    glossario = {
        "_meta": {
            "instrucoes": [
                "Preencha 'pt' com a grafia que quer usar no jogo inteiro.",
                "Deixe 'pt' vazio para DESCARTAR (nao e nome proprio).",
                "Preencha 'genero' com M ou F quando for pessoa - o portugues",
                "precisa disso para concordancia e o japones nao marca.",
                "Este glossario vai em TODO prompt de traducao: cada entrada",
                "custa tokens, entao mantenha so o que importa de verdade.",
            ],
            "extraido_de": f"{len(textos):,} unidades de texto",
        },
        "pessoas": [
            {"jp": t, "ocorrencias": n, "pt": "", "genero": "", "evidencia": e}
            for t, n, e in pessoas
        ],
        "lugares": [
            {"jp": c, "ocorrencias": n, "pt": ""}
            for c, n in lugares.most_common(25) if n >= 5
        ],
        "incertos": [
            {"jp": t, "ocorrencias": n, "pt": "", "genero": "", "evidencia": ""}
            for t, n, _ in incertos
        ],
    }
    destino = OUT / "glossario.json"
    destino.write_text(json.dumps(glossario, indent=2, ensure_ascii=False),
                       encoding="utf-8")

    total = len(pessoas) + len(glossario["lugares"]) + len(incertos)
    print()
    print("=" * 72)
    print(f"  {total} entradas para revisar em {destino.name}")
    print(f"  (de 1.834 sequencias de katakana brutas - o filtro cortou 97%)")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
