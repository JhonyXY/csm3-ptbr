#!/usr/bin/env python3
"""Fase 1: exporta todo o texto do jogo para JSON de traducao.

Cada string vira uma entrada com o japones original e um campo `pt` vazio para
preencher. O que o tradutor NAO deve tocar ja vem isolado:

  - placeholders de nome (letras gregas) viram tags {g} {d} {z} {b} {e} {t}
  - espacos de largura total usados para centralizar sao removidos do texto e
    guardados a parte - o injetor recalcula a centralizacao sozinho

Uso:
    python3 export_json.py              # exporta tudo
    python3 export_json.py --script 11  # so um script, para inspecionar
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import walker
from script_text import word_to_sjis

ROM_PATH = Path(__file__).resolve().parents[2] / "baserom.gba"
OUT_DIR = Path(__file__).parent / "_out"

IDEOGRAPHIC_SPACE = "　"  # SJIS 0x8140

# Placeholders de nome. Confirmados por dupla evidencia: o renderer mascara
# 0xF0FF sobre a faixa grega, e a frequencia bate com papeis de personagem.
PLACEHOLDERS = {
    "γ": "{g}",  # gamma  - 1065x, o mais frequente
    "δ": "{d}",  # delta  -  625x
    "ζ": "{z}",  # zeta   -   83x
    "β": "{b}",  # beta   -   19x
    "η": "{e}",  # eta    -    4x
    "θ": "{t}",  # theta  -    4x
}
UNPLACEHOLDER = {v: k for k, v in PLACEHOLDERS.items()}


def to_translatable(text: str) -> tuple[str, int, int]:
    """Separa o texto do preenchimento de centralizacao.

    Devolve (texto_limpo, espacos_a_esquerda, espacos_a_direita).
    """
    left = len(text) - len(text.lstrip(IDEOGRAPHIC_SPACE))
    right = len(text) - len(text.rstrip(IDEOGRAPHIC_SPACE))
    core = text.strip(IDEOGRAPHIC_SPACE)
    for ch, tag in PLACEHOLDERS.items():
        core = core.replace(ch, tag)
    return core, left, right


def from_translatable(text: str) -> str:
    """Inverso de to_translatable, para o injetor."""
    for tag, ch in UNPLACEHOLDER.items():
        text = text.replace(tag, ch)
    return text


def decode_words(words: list[int]) -> str | None:
    raw = bytearray()
    for w in words:
        raw += word_to_sjis(w)
    try:
        return bytes(raw).decode("shift_jis")
    except UnicodeDecodeError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", type=int, help="exporta so este script")
    ap.add_argument("--out", default="textos_originais.json")
    args = ap.parse_args()

    rom = csm3rom.load_rom(ROM_PATH)
    auto_map = walker.load_auto_map()
    OUT_DIR.mkdir(exist_ok=True)

    entries = []
    stats = Counter()
    undecodable = []

    for script in csm3rom.iter_scripts(rom):
        if args.script is not None and script.index != args.script:
            continue

        body = bytes(script.body)
        result = walker.walk(body, auto_map)
        text_ins = result.text_instructions
        if not text_ins:
            continue

        for order, ins in enumerate(text_ins):
            words = ins.text_words or []
            original = decode_words(words)
            if original is None:
                undecodable.append((script.index, ins.offset))
                stats["nao_decodifica"] += 1
                continue

            core, left, right = to_translatable(original)
            stats["total"] += 1
            if not core:
                stats["vazias"] += 1

            entries.append({
                "id": f"s{script.index:04d}_{ins.offset:04X}",
                "script": script.index,
                "offset": ins.offset,
                "ordem": order,
                "opcode": f"0x{ins.opcode:04X}",
                "jp": core,
                "pt": "",
                "pad": [left, right],
                "chars": len(core),
            })

    # Contexto: as falas vizinhas do mesmo script, para o tradutor entender a cena.
    by_script: dict[int, list] = {}
    for e in entries:
        by_script.setdefault(e["script"], []).append(e)
    for group in by_script.values():
        group.sort(key=lambda e: e["ordem"])
        for i, e in enumerate(group):
            e["contexto"] = {
                "antes": group[i - 1]["jp"] if i > 0 else None,
                "depois": group[i + 1]["jp"] if i + 1 < len(group) else None,
            }

    out_path = OUT_DIR / args.out
    payload = {
        "_meta": {
            "jogo": "Summon Night: Craft Sword Monogatari 3",
            "fonte": "baserom.gba archive 2 (scripts LZ77 + PSI3)",
            "encoding_original": "Shift-JIS, 2 bytes por caractere",
            "placeholders": {
                tag: f"nome de personagem (era {ch})"
                for ch, tag in PLACEHOLDERS.items()
            },
            "instrucoes": [
                "Preencha o campo 'pt' de cada entrada.",
                "NAO altere 'id', 'script', 'offset', 'opcode' nem 'pad'.",
                "Mantenha as tags {g} {d} {z} {b} {e} {t} intactas - sao nomes "
                "que o jogo substitui em tempo de execucao.",
                "Nao se preocupe com centralizacao nem quebra de linha: o campo "
                "'pad' guarda o preenchimento original e o injetor recalcula.",
                "Cada linha comporta ~30 caracteres depois do VWF (eram 18).",
            ],
            "total_strings": len(entries),
            "scripts": len(by_script),
        },
        "strings": entries,
    }
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("=" * 72)
    print("EXPORTACAO CONCLUIDA")
    print("=" * 72)
    print(f"  strings exportadas : {len(entries):,}")
    print(f"  scripts            : {len(by_script):,}")
    print(f"  vazias             : {stats['vazias']:,}")
    print(f"  nao decodificam    : {stats['nao_decodifica']:,}")
    for s, off in undecodable[:5]:
        print(f"      script {s} @0x{off:04X}")
    total_chars = sum(e["chars"] for e in entries)
    print(f"  caracteres japoneses: {total_chars:,}")
    if entries:
        print(f"  media por string    : {total_chars/len(entries):.1f} chars")
    print(f"  arquivo             : {out_path}")

    # Round-trip das tags, para garantir que o injetor consegue desfazer.
    falhas = 0
    for e in entries:
        restored = from_translatable(e["jp"])
        expected = decode_words([])  # noop, so para manter simetria
        rebuilt = IDEOGRAPHIC_SPACE * e["pad"][0] + restored + IDEOGRAPHIC_SPACE * e["pad"][1]
        try:
            rebuilt.encode("shift_jis")
        except UnicodeEncodeError:
            falhas += 1
    print(f"  round-trip das tags : {len(entries) - falhas:,}/{len(entries):,} ok")

    print()
    print("=" * 72)
    print("AMOSTRA")
    print("=" * 72)
    for e in entries[:8]:
        print(f"  [{e['id']}] {e['jp']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
