#!/usr/bin/env python3
"""Renderiza palavras acentuadas com a tabela NOVA, para conferir antes do teste.

Reproduz exatamente o que src/ptbr_blit.c faz:
  - desenha as colunas [recuo, recuo+largura) do glifo
  - encosta a primeira coluna de tinta na posicao x
  - avanca o que a tabela manda

Se o til aparecer aqui, aparece no jogo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import font as fontmod
import patch_acentos
from acentos import NECESSARIAS

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"

LARGURA_TELA = 120
ALTURA = 15
MARGEM_TOPO = 2

SJIS = {}
for _i in range(26):
    SJIS[chr(ord("A") + _i)] = 0x8260 + _i
    SJIS[chr(ord("a") + _i)] = 0x8281 + _i
SJIS["?"] = 0x8148
SJIS[" "] = 0x8140


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    h, _ = fontmod.read_font_header(rom)
    w, hh = h["width"], h["height"]
    dados = rom[h["data_offset"]: h["data_offset"] + h["data_size"]]
    count = h["data_size"] // (fontmod.glyph_bytes_per_row(w) * hh)

    tabela = (OUT / "larguras.bin").read_bytes()
    slots = json.loads((OUT / "acentos_slots.json").read_text(encoding="utf-8"))
    inicio = slots["inicio"]

    # indice de glifo para cada caractere
    idx_de = {}
    rows_de = {}
    for ch, code in SJIS.items():
        i = fontmod.sjis_to_glyph_index(rom, code)
        if i is not None and i < count:
            idx_de[ch] = i
            rows_de[ch] = fontmod.decode_glyph(dados, i, w, hh)
    for k, (ch, base, acento) in enumerate(NECESSARIAS):
        r = patch_acentos.compor(rom, dados, w, hh, count, base, acento)
        if r is not None:
            idx_de[ch] = inicio + k
            rows_de[ch] = r

    def bordas(rows):
        a = b = None
        for r in rows:
            for c, px in enumerate(r):
                if px == "#":
                    a = c if a is None or c < a else a
                    b = c if b is None or c > b else b
        return a, b

    for frase in ("Não", "Sim", "Salvar?", "Coração", "Você é único"):
        tela = [[" "] * LARGURA_TELA for _ in range(ALTURA)]
        x = 1
        detalhes = []
        for ch in frase:
            if ch not in rows_de:
                x += 4
                detalhes.append(f"{ch}=?")
                continue
            rows = rows_de[ch]
            i = idx_de[ch]
            avanco = tabela[i] if i < len(tabela) else 12
            a, b = bordas(rows)
            recuo = a if a is not None else 0
            larg = (b - a + 1) if a is not None else 0
            detalhes.append(f"{ch}(av{avanco},re{recuo},tt{larg})")
            for ln in range(12):
                for col in range(recuo, min(recuo + larg, 12)):
                    if rows[ln][col] != "#":
                        continue
                    px, py = x + col - recuo, ln + MARGEM_TOPO
                    if 0 <= px < LARGURA_TELA and py < ALTURA:
                        tela[py][px] = "#"
                    if px + 1 < LARGURA_TELA and py < ALTURA and \
                            tela[py][px + 1] == " ":
                        tela[py][px + 1] = "."
            x += avanco

        print("=" * 74)
        print(f'"{frase}"   largura {x - 1}px')
        print("  " + "  ".join(detalhes))
        print("=" * 74)
        for linha in tela:
            s = "".join(linha).rstrip()
            if s:
                print("  " + s)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
