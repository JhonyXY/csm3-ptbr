#!/usr/bin/env python3
"""Monta o glossario final, cruzando a extracao dos dados com a pesquisa.

A pesquisa foi ate a ROM como fonte primaria e confirmou nomes, papeis e -
criticamente - o GENERO de cada personagem, que o portugues exige e o japones
nao marca. O que ela confirmou entra preenchido; o resto fica para revisao.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

OUT = Path(__file__).parent / "_out"

# Grafias da traducao inglesa de fas (github.com/salixa/SNSC3-Translation, o
# glossario oficial da equipe) - e o que a comunidade reconhece e o que aparece
# em qualquer guia. Genero confirmado por ja.wikipedia e pelo texto do jogo.
CONFIRMADOS = {
    # --- protagonistas (o jogador escolhe um) ---
    "リッチバーン": ("Ritchburn", "M", "protagonista masculino, 13 anos"),
    "リッチー":     ("Ritchie", "M", "apelido padrao do protagonista"),
    "リフモニカ":   ("Rifmonica", "F", "protagonista feminina, 13 anos"),
    "リフ":         ("Rif", "F", "apelido padrao da protagonista"),

    # --- os 4 parceiros (護衛獣) ---
    # ATENCAO: o patch ingles grafa "Run-dor". Em portugues isso se le
    # "run-DOR", que evoca dor - ruim para um personagem. Ver DECISOES.
    "ランドル":     ("Randol", "M", "soldado-maquina; katakana truncado; patch EN: Run-dor"),
    "エンジ":       ("Enzi", "M", "tigre-youkai com cara de gato; usa ワガハイ"),
    "キルフィス":   ("Killfith", "M", "frio e calado; sem tique de fala"),
    "ルフィール":   ("Rufeel", "F", "unica femea; medrosa que se faz de durona; usa ～わ"),

    # --- elenco ---
    "ミューノ":     ("Murno", "F", "garota misteriosa protegida pelo heroi"),
    "ロブ":         ("Rob", "M", "mestre-ferreiro falecido"),
    "ヴィー":       ("V.E", "F", "mestra da oficina Rob; grafia lida dos bytes do patch"),
    "ボスタフ":     ("Bostaph", "M", "mestre da oficina rival"),
    "レミィ":       ("Lemmy", "M", "jovem ferreiro da oficina Bostaph"),
    "ジェイド":     ("Jade", "M", "ferreiro da oficina Benson; 'o Imortal Jade'"),
    "アニス":       ("Anise", "F", "do grupo que persegue Murno"),
    "パイク":       ("Pike", "M", "guerreiro do mesmo grupo; 'Pike de Aco'"),
    "ギラン":       ("Gillan", "M", "membro do mesmo grupo; 'o Belo Gillan'"),
    "ティエ":       ("Tier", "F", "filha da estalagem"),

    # --- lugares (grafia do patch ingles onde existe) ---
    "ディックル村":   ("Vila Deckell", "", "lugar"),
    "ディックル鉱洞": ("Mina de Deckell", "", "lugar"),
    "ルイーズ村":     ("Vila Louise", "", "lugar"),
    "スポート洞":     ("Caverna Sport", "", "lugar"),
    "ミシュース村":   ("Vila Mishus", "", "lugar"),
    "フラード洞":     ("Caverna Flard", "", "lugar"),
    "マーネイル":     ("Estacao Marneil", "", "lugar (posto de parada)"),
    "プロスバン":     ("Prosban", "", "lugar"),
    "スレンジ":       ("Slenj", "", "lugar (mina)"),
    "リィンバウム":   ("Lyndbaum", "", "o mundo do jogo; grafia oficial da Atlus"),
}

# Lidos direto dos bytes do patch v1.0 aplicado - autoritativo.
DO_PATCH = {
    "ゴヴァン":     ("Gunvald", "", "lido do patch (NAO era 'Govan')"),
    "ザック":       ("Zakk", "", "lido do patch"),
    "マグドラド":   ("Magdrad", "", "lido do patch"),
    "トラム":       ("Tram", "", "lido do patch"),
    "サージ":       ("Serj", "", "lido do patch"),
    "ソードボルト": ("Swordbolt", "", "lido do patch"),
    "ベルヴォレン": ("Velworen", "", "lido do patch (NAO era 'Belvoren')"),
}

# Sem fonte: nem no patch nem em wiki confiavel. Romanizacao e palpite meu.
SEM_FONTE = {
    "ウェルマン": "Wellman", "ベンソン": "Benson",
    "エリエ": "Erie", "ヴォイジン": "Voijin",
    "ギャラハン": "Gallahan", "アカバネ": "Akabane",
    "イアナ": "Iana", "レクイ": "Rekui", "キッカ": "Kikka", "リュート": "Lute",
}


def main() -> int:
    bruto = json.loads((OUT / "glossario.json").read_text(encoding="utf-8"))
    ocorrencias = {}
    for secao in ("pessoas", "lugares", "incertos"):
        for e in bruto.get(secao, []):
            ocorrencias[e["jp"]] = e["ocorrencias"]

    confirmados, revisar = [], []

    for jp, (pt, genero, nota) in CONFIRMADOS.items():
        confirmados.append({
            "jp": jp, "pt": pt, "genero": genero,
            "ocorrencias": ocorrencias.get(jp, 0),
            "nota": nota, "fonte": "patch v1.0 + glossario da equipe",
        })

    for jp, (pt, genero, nota) in DO_PATCH.items():
        confirmados.append({
            "jp": jp, "pt": pt, "genero": genero,
            "ocorrencias": ocorrencias.get(jp, 0),
            "nota": nota, "fonte": "bytes do patch v1.0",
        })

    for jp, sugestao in SEM_FONTE.items():
        revisar.append({
            "jp": jp, "pt": sugestao, "genero": "",
            "ocorrencias": ocorrencias.get(jp, 0),
            "nota": "romanizacao SUGERIDA, sem fonte - confirme a grafia",
            "fonte": "sugestao",
        })

    confirmados.sort(key=lambda e: -e["ocorrencias"])
    revisar.sort(key=lambda e: -e["ocorrencias"])

    print("=" * 72)
    print("GLOSSARIO FINAL")
    print("=" * 72)
    print(f"\n  CONFIRMADOS pela pesquisa ({len(confirmados)}):")
    print(f"  {'ocorr':>6}  {'japones':<14} {'portugues':<14} {'gen':<4} nota")
    for e in confirmados:
        if e["ocorrencias"] or e["genero"]:
            print(f"  {e['ocorrencias']:6,d}  {e['jp']:<14} {e['pt']:<14} "
                  f"{e['genero'] or '-':<4} {e['nota'][:34]}")

    print(f"\n  PARA VOCE REVISAR ({len(revisar)}) - grafia sugerida, sem fonte:")
    for e in revisar:
        if e["ocorrencias"] >= 20:
            print(f"  {e['ocorrencias']:6,d}  {e['jp']:<14} {e['pt']:<14} "
                  f"{'?':<4} confirme grafia e genero")

    final = {
        "_meta": {
            "uso": "injetado em todo prompt de traducao para fixar os nomes",
            "instrucoes": [
                "Os CONFIRMADOS vieram da ROM e de wikipedia - o genero e dado duro.",
                "O campo 'pt' e sugestao de adaptacao: mude se preferir outra grafia.",
                "Os de REVISAR nao tem fonte; a romanizacao e palpite fundamentado.",
                "Genero em branco = lugar ou coisa (nao precisa concordancia).",
            ],
        },
        "confirmados": confirmados,
        "revisar": revisar,
    }
    destino = OUT / "glossario_final.json"
    destino.write_text(json.dumps(final, indent=2, ensure_ascii=False),
                       encoding="utf-8")

    com_genero = sum(1 for e in confirmados if e["genero"])
    cobertura = sum(e["ocorrencias"] for e in confirmados)
    print()
    print("=" * 72)
    print(f"  {len(confirmados)} confirmados, {com_genero} com genero definido")
    print(f"  cobrem {cobertura:,} ocorrencias no texto do jogo")
    print(f"  gravado: {destino.name}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
