#!/usr/bin/env python3
"""Extrai candidatos a nome proprio das 21.062 falas.

Nome proprio traduzido de forma inconsistente e o defeito mais visivel de
traducao automatica de RPG: o mesmo personagem vira tres nomes diferentes em
tres cenas. A defesa e fixar o glossario ANTES e injeta-lo em cada prompt.

Sinais usados para achar os candidatos:
  1. sequencias de KATAKANA - em japones, nomes proprios e estrangeirismos sao
     escritos em katakana, entao uma sequencia repetida e forte candidata
  2. palavras seguidas de HONORIFICO (さん ちゃん くん 様 殿) - so pessoa recebe
  3. sequencias de kanji seguidas de sufixo de LUGAR (村 町 山 洞 城 島 国)
  4. vizinhanca dos PLACEHOLDERS de nome - quem aparece perto de {g}/{d} tende
     a ser personagem
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

OUT = Path(__file__).parent / "_out"

KATAKANA = re.compile(r"[ァ-ヶー]{2,}")
HONORIFICOS = ("さん", "ちゃん", "くん", "君", "様", "さま", "殿")
SUFIXOS_LUGAR = ("村", "町", "山", "洞", "城", "島", "国", "街", "森", "谷", "塔")
KANJI = re.compile(r"[一-鿿]{2,}")

# Katakana que sao palavras comuns, nao nomes proprios.
COMUNS = {
    "アイテム", "レベル", "ポイント", "セーブ", "ロード", "データ", "システム",
    "パートナー", "メニュー", "ボタン", "ゲーム", "テスト", "サウンド", "バージョン",
    "コマンド", "タイプ", "モード", "スタート", "エンディング", "オープニング",
    "クリア", "ミス", "ダメージ", "エネルギー", "パワー", "スピード", "チェック",
    "メッセージ", "ウィンドウ", "カーソル", "リスト", "グループ", "スキル",
}


def main() -> int:
    dados = json.loads((OUT / "falas_originais.json").read_text(encoding="utf-8"))
    unidades = dados["falas"] + dados["itens"]
    textos = [u["jp"] for u in unidades]
    corpus = "\n".join(textos)

    print("=" * 72)
    print("CANDIDATOS A NOME PROPRIO")
    print("=" * 72)
    print(f"  analisando {len(textos):,} unidades de texto")

    # --- 1. katakana ---
    kata = Counter()
    for t in textos:
        for m in KATAKANA.findall(t):
            if m not in COMUNS and len(m) >= 2:
                kata[m] += 1

    print()
    print("-" * 72)
    print("1. SEQUENCIAS DE KATAKANA (nomes e estrangeirismos)")
    print("-" * 72)
    print(f"  distintas: {len(kata):,}")
    print(f"  {'ocorr':>6}  termo")
    for termo, n in kata.most_common(40):
        print(f"  {n:6,d}  {termo}")

    # --- 2. honorificos: quem vem antes e pessoa ---
    pessoas = Counter()
    for t in textos:
        for h in HONORIFICOS:
            for m in re.finditer(re.escape(h), t):
                antes = t[max(0, m.start() - 6):m.start()]
                nome = re.search(r"([ァ-ヶー一-鿿]{2,})$", antes)
                if nome:
                    pessoas[nome.group(1)] += 1

    print()
    print("-" * 72)
    print("2. PRECEDIDOS DE HONORIFICO (sao pessoas)")
    print("-" * 72)
    for termo, n in pessoas.most_common(25):
        print(f"  {n:6,d}  {termo}")

    # --- 3. lugares ---
    lugares = Counter()
    for t in textos:
        for suf in SUFIXOS_LUGAR:
            for m in re.finditer(re.escape(suf), t):
                antes = t[max(0, m.start() - 6):m.start()]
                nome = re.search(r"([ァ-ヶー一-鿿]{1,})$", antes)
                if nome and len(nome.group(1)) >= 2:
                    lugares[nome.group(1) + suf] += 1

    print()
    print("-" * 72)
    print("3. TOPONIMOS (sufixo de lugar)")
    print("-" * 72)
    for termo, n in lugares.most_common(25):
        print(f"  {n:6,d}  {termo}")

    # --- 4. quem convive com os placeholders de nome ---
    vizinhos = Counter()
    for t in textos:
        if "{g}" not in t and "{d}" not in t:
            continue
        for m in KATAKANA.findall(t):
            if m not in COMUNS:
                vizinhos[m] += 1

    print()
    print("-" * 72)
    print("4. APARECEM JUNTO DOS PLACEHOLDERS {g}/{d} (elenco principal)")
    print("-" * 72)
    for termo, n in vizinhos.most_common(20):
        print(f"  {n:6,d}  {termo}")

    # --- 5. kanji compostos frequentes (termos de sistema) ---
    compostos = Counter()
    for t in textos:
        for m in KANJI.findall(t):
            if 2 <= len(m) <= 4:
                compostos[m] += 1

    print()
    print("-" * 72)
    print("5. COMPOSTOS DE KANJI FREQUENTES (termos de jogo)")
    print("-" * 72)
    for termo, n in compostos.most_common(30):
        print(f"  {n:6,d}  {termo}")

    # --- grava para revisao ---
    glossario = {
        "_meta": {
            "origem": "extraido de falas_originais.json",
            "instrucoes": [
                "Revise cada entrada e preencha 'pt'.",
                "Deixe 'pt' vazio para descartar (nao e nome proprio).",
                "Este glossario e injetado em TODO prompt de traducao, entao",
                "cada entrada custa tokens - mantenha so o que importa.",
            ],
        },
        "personagens": [
            {"jp": t, "ocorrencias": n, "pt": "", "nota": ""}
            for t, n in kata.most_common(60)
        ],
        "com_honorifico": [
            {"jp": t, "ocorrencias": n, "pt": "", "nota": "precedido de honorifico"}
            for t, n in pessoas.most_common(30)
        ],
        "lugares": [
            {"jp": t, "ocorrencias": n, "pt": "", "nota": ""}
            for t, n in lugares.most_common(30)
        ],
        "termos": [
            {"jp": t, "ocorrencias": n, "pt": "", "nota": ""}
            for t, n in compostos.most_common(40)
        ],
    }
    destino = OUT / "glossario.json"
    destino.write_text(json.dumps(glossario, indent=2, ensure_ascii=False),
                       encoding="utf-8")

    total = sum(len(v) for k, v in glossario.items() if k != "_meta")
    print()
    print("=" * 72)
    print(f"  {total} candidatos gravados em {destino.name}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
