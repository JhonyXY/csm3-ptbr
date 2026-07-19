#!/usr/bin/env python3
"""O cirilico serve de porta para as acentuadas?

Ideia: em vez de criar codigos Shift-JIS novos e mexer na tabela de lookup,
reaproveitar codigos que JA tem glifo e que o jogo nunca usa. O cirilico
(SJIS 0x8440-0x8491) e candidato natural:

  - decodifica sem erro em Python (nao quebra o round-trip do pipeline)
  - o jogo nao usa nenhum deles no texto
  - ja tem glifo, entao basta SOBRESCREVER o bitmap - a tabela de lookup fica
    intocada

Se confirmar, o patch das acentuadas vira so troca de bitmap na fonte.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import font as fontmod

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"

# Faixas candidatas em Shift-JIS.
FAIXAS = [
    ("cirilico maiusculo", 0x8440, 0x8460),
    ("cirilico minusculo", 0x8470, 0x8491),
    ("grego maiusculo", 0x839F, 0x83B6),
]


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    header, _ = fontmod.read_font_header(rom)
    w, h = header["width"], header["height"]
    data = rom[header["data_offset"]: header["data_offset"] + header["data_size"]]
    count = header["data_size"] // (fontmod.glyph_bytes_per_row(w) * h)

    # Quais codigos o jogo realmente usa?
    usados = set()
    caminho = OUT / "textos_originais.json"
    if caminho.exists():
        d = json.loads(caminho.read_text(encoding="utf-8"))
        for e in d["strings"]:
            for ch in e["jp"]:
                try:
                    par = ch.encode("shift_jis")
                except UnicodeEncodeError:
                    continue
                if len(par) == 2:
                    usados.add((par[0] << 8) | par[1])

    print("=" * 72)
    print("FAIXAS CANDIDATAS PARA AS ACENTUADAS")
    print("=" * 72)

    melhor = None
    for nome, lo, hi in FAIXAS:
        com_glifo = 0
        em_uso = 0
        decodifica = 0
        indices = []
        for code in range(lo, hi + 1):
            par = bytes((code >> 8, code & 0xFF))
            try:
                par.decode("shift_jis")
                decodifica += 1
            except UnicodeDecodeError:
                continue
            idx = fontmod.sjis_to_glyph_index(rom, code)
            if idx is not None and idx < count:
                com_glifo += 1
                indices.append((code, idx))
            if code in usados:
                em_uso += 1

        total = hi - lo + 1
        print(f"\n  {nome} (0x{lo:04X}-0x{hi:04X}, {total} codigos)")
        print(f"      decodificam em Python : {decodifica}")
        print(f"      tem glifo na fonte    : {com_glifo}")
        print(f"      USADOS pelo jogo      : {em_uso}")
        if em_uso == 0 and com_glifo >= 25:
            print(f"      => SERVE ({com_glifo} glifos disponiveis)")
            if melhor is None:
                melhor = (nome, indices)
        elif em_uso:
            print(f"      => nao serve, o jogo usa")
        else:
            print(f"      => poucos glifos")

    if not melhor:
        print("\n  Nenhuma faixa serve inteira.")
        return 1

    nome, indices = melhor
    print()
    print("=" * 72)
    print(f"ESCOLHIDA: {nome}")
    print("=" * 72)
    print(f"  {len(indices)} codigos com glifo, nenhum usado pelo jogo.")
    print("  Sobrescrevendo o bitmap desses glifos, a tabela de lookup fica")
    print("  INTOCADA - o patch vira so troca de bytes na fonte.")
    print()
    print("  primeiros pares (codigo SJIS -> indice de glifo):")
    for code, idx in indices[:8]:
        ch = bytes((code >> 8, code & 0xFF)).decode("shift_jis")
        print(f"      0x{code:04X} '{ch}' -> glifo {idx}")

    # Mostra um glifo atual para confirmar que e mesmo cirilico/grego.
    if indices:
        code, idx = indices[0]
        ch = bytes((code >> 8, code & 0xFF)).decode("shift_jis")
        print(f"\n  glifo atual de 0x{code:04X} ('{ch}'):")
        for r in fontmod.decode_glyph(data, idx, w, h):
            print(f"      {r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
