#!/usr/bin/env python3
"""Fase 1 (v2): exporta o texto agrupado por FALA, nao por linha.

As 41.961 strings do jogo sao linhas ja quebradas para caber na caixa (media de
9,1 caracteres, maximo 18). Traduzir linha a linha entrega ao modelo frases
cortadas no meio. Este exportador agrupa as linhas contiguas de uma mesma
mensagem numa unidade de traducao completa.

A caixa comporta 3 linhas (verificado: nenhum bloco passa disso em 21 mil).
Cada fala carrega a estrutura original para o injetor saber re-quebrar depois.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import walker
from export_json import PLACEHOLDERS, IDEOGRAPHIC_SPACE
from script_text import word_to_sjis

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"

# Opcodes de FALA: linhas consecutivas formam uma mensagem.
OPS_FALA = {0x0308, 0x0363, 0x0311, 0x0317}
# Opcodes de ITEM: cada um e uma opcao independente.
OPS_ITEM = {0x0314, 0x030D, 0x0307, 0x030B, 0x0316}

LINHAS_POR_CAIXA = 3
LARGURA_FIXA = 18      # caracteres por linha hoje (12px)
LARGURA_VWF = 26       # caracteres por linha com VWF quantizado (8,58px)


def decodificar(words: list[int]) -> str | None:
    raw = bytearray()
    for w in words:
        raw += word_to_sjis(w)
    try:
        return bytes(raw).decode("shift_jis")
    except UnicodeDecodeError:
        return None


def limpar(texto: str) -> tuple[str, int, int]:
    esq = len(texto) - len(texto.lstrip(IDEOGRAPHIC_SPACE))
    dir_ = len(texto) - len(texto.rstrip(IDEOGRAPHIC_SPACE))
    nucleo = texto.strip(IDEOGRAPHIC_SPACE)
    for ch, tag in PLACEHOLDERS.items():
        nucleo = nucleo.replace(ch, tag)
    return nucleo, esq, dir_


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    auto_map = walker.load_auto_map()
    OUT.mkdir(exist_ok=True)

    falas = []
    itens = []
    stats = Counter()

    for script in csm3rom.iter_scripts(rom):
        result = walker.walk(bytes(script.body), auto_map)

        bloco: list[dict] = []
        fim_anterior = None

        def fechar():
            nonlocal bloco
            if not bloco:
                return
            texto = "".join(l["jp"] for l in bloco)
            falas.append({
                "id": f"f{script.index:04d}_{bloco[0]['offset']:04X}",
                "script": script.index,
                "offset": bloco[0]["offset"],
                "linhas": len(bloco),
                "jp": texto,
                "pt": "",
                "chars": len(texto),
                "estrutura": [
                    {"offset": l["offset"], "opcode": l["opcode"],
                     "pad": l["pad"], "chars": len(l["jp"])}
                    for l in bloco
                ],
            })
            stats[f"bloco_{len(bloco)}_linhas"] += 1
            bloco = []

        for ins in result.instructions:
            if not ins.is_text:
                if fim_anterior is not None and ins.offset == fim_anterior:
                    pass
                fechar()
                fim_anterior = None
                continue

            texto = decodificar(ins.text_words or [])
            if texto is None:
                stats["nao_decodifica"] += 1
                continue
            nucleo, esq, dir_ = limpar(texto)

            if ins.opcode in OPS_ITEM:
                fechar()
                itens.append({
                    "id": f"i{script.index:04d}_{ins.offset:04X}",
                    "script": script.index,
                    "offset": ins.offset,
                    "opcode": f"0x{ins.opcode:04X}",
                    "jp": nucleo,
                    "pt": "",
                    "pad": [esq, dir_],
                    "chars": len(nucleo),
                })
                fim_anterior = ins.offset + ins.size
                continue

            if fim_anterior is not None and ins.offset != fim_anterior:
                fechar()
            bloco.append({"offset": ins.offset, "opcode": f"0x{ins.opcode:04X}",
                          "jp": nucleo, "pad": [esq, dir_]})
            fim_anterior = ins.offset + ins.size

        fechar()

    # Contexto: a fala anterior e a seguinte do mesmo script.
    por_script: dict[int, list] = {}
    for f in falas:
        por_script.setdefault(f["script"], []).append(f)
    for grupo in por_script.values():
        grupo.sort(key=lambda f: f["offset"])
        for i, f in enumerate(grupo):
            f["contexto"] = {
                "antes": grupo[i - 1]["jp"] if i > 0 else None,
                "depois": grupo[i + 1]["jp"] if i + 1 < len(grupo) else None,
            }

    print("=" * 72)
    print("EXPORTACAO POR FALA")
    print("=" * 72)
    print(f"  falas   : {len(falas):,}")
    print(f"  itens de menu: {len(itens):,}")
    print(f"  total de unidades de traducao: {len(falas)+len(itens):,}")
    print(f"  (antes, linha a linha: 41.961)")
    print()
    for k in sorted(stats):
        print(f"      {k}: {stats[k]:,}")

    chars = [f["chars"] for f in falas]
    if chars:
        print()
        print(f"  caracteres por fala: min {min(chars)} / mediana "
              f"{sorted(chars)[len(chars)//2]} / max {max(chars)}")
        print(f"  total: {sum(chars):,} caracteres japoneses")

    # --- O ponto critico: quanto vai estourar? ---
    print()
    print("=" * 72)
    print("PREVISAO DE OVERFLOW (expansao 2,2x para portugues)")
    print("=" * 72)
    cap_fixa = LINHAS_POR_CAIXA * LARGURA_FIXA
    cap_vwf = LINHAS_POR_CAIXA * LARGURA_VWF
    print(f"  capacidade da caixa: {LINHAS_POR_CAIXA} linhas")
    print(f"      hoje (12px)   : {LARGURA_FIXA} chars/linha = {cap_fixa} por caixa")
    print(f"      com VWF       : {LARGURA_VWF} chars/linha = {cap_vwf} por caixa")
    print()
    for nome, cap in (("sem VWF", cap_fixa), ("com VWF", cap_vwf)):
        estoura = sum(1 for c in chars if c * 2.2 > cap)
        caixas_extras = sum(max(0, int(c * 2.2 / cap)) for c in chars)
        print(f"  {nome}: {estoura:,} falas estouram "
              f"({100*estoura/len(chars):.1f}%), "
              f"~{caixas_extras:,} caixas extras necessarias")

    payload = {
        "_meta": {
            "jogo": "Summon Night: Craft Sword Monogatari 3",
            "unidade": "fala completa (linhas contiguas agrupadas)",
            "linhas_por_caixa": LINHAS_POR_CAIXA,
            "largura_por_linha": {"fixa_12px": LARGURA_FIXA, "vwf": LARGURA_VWF},
            "placeholders": {tag: "nome de personagem" for tag in PLACEHOLDERS.values()},
            "instrucoes": [
                "Traduza o campo 'jp' para 'pt'. NAO quebre em linhas - o injetor",
                "faz a quebra medindo a largura real de cada glifo.",
                "Mantenha as tags {g} {d} {z} {b} {e} {t} intactas.",
                "'estrutura' descreve como o original estava quebrado; o injetor",
                "usa isso para saber quantas caixas cabem.",
            ],
            "falas": len(falas),
            "itens": len(itens),
        },
        "falas": falas,
        "itens": itens,
    }
    destino = OUT / "falas_originais.json"
    destino.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                       encoding="utf-8")
    print(f"\n  gravado: {destino}")

    print()
    print("=" * 72)
    print("AMOSTRA - falas de 3 linhas remontadas")
    print("=" * 72)
    mostrados = 0
    for f in falas:
        if f["linhas"] < 3:
            continue
        print(f"\n  [{f['id']}] {f['linhas']} linhas, {f['chars']} chars")
        for l in f["estrutura"]:
            print(f"      linha @0x{l['offset']:04X} ({l['chars']} chars)")
        print(f"      => {f['jp']}")
        mostrados += 1
        if mostrados >= 5:
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
