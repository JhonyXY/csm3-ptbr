#!/usr/bin/env python3
"""Compoe os glifos acentuados a partir das letras que ja existem na fonte.

A fonte tem 2.144 glifos de 12x12 (1bpp, 24 bytes cada) e 846 nao aparecem em
nenhum dialogo - sao kanji que a traducao nao vai usar. Da para sobrescrever
esses slots com as acentuadas SEM crescer nada.

O acento e desenhado por cima da letra base. Se nao couber, a letra desce alguns
pixels antes.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import font as fontmod
import script_text

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"

# Desenhos dos acentos, alinhados a esquerda. Cada string e uma linha de pixels.
ACENTOS = {
    "agudo":      ["...##", "..##.", ".##.."],
    "grave":      ["##...", ".##..", "..##."],
    "circunflexo": ["..#..", ".###.", "##.##"],
    "til":        [".##.#", "#.##."],
    "trema":      ["##.##", "##.##"],
}

# Versoes compactas de 2 linhas, para as MAIUSCULAS.
# Minusculas ocupam as linhas 4-9 e tem 4 livres em cima: cabe acento de 3
# linhas mais respiro. Maiusculas ocupam 1-9 e so tem 1 livre - com acento de
# 3 linhas a letra desceria 3 e perderia o rodape (o 'E' virava 'F').
ACENTOS_MAIUSCULA = {
    "agudo":      ["..##", ".##."],
    "grave":      ["##..", ".##."],
    "circunflexo": [".##.", "#..#"],
    "til":        [".##.#", "#.##."],
    "trema":      ["##.##", "....."],
}

# Cedilha: desenhada ABAIXO da letra. Encosta de proposito - e como cedilha e.
CEDILHA = ["..##.", "...#.", "..##."]

# Linhas de respiro entre o acento e a letra. Sem isso o til encosta no 'a' e
# os dois viram uma mancha so na tela.
RESPIRO = 1


def desenho_do_acento(acento: str, base_letra: str) -> list[str]:
    """Escolhe a versao do acento conforme a altura disponivel na letra."""
    if base_letra.isupper():
        return ACENTOS_MAIUSCULA[acento]
    return ACENTOS[acento]

# Quais acentuadas o portugues precisa, e como compor cada uma.
NECESSARIAS = [
    # (caractere, letra base, acento)
    ("á", "a", "agudo"), ("à", "a", "grave"),
    ("â", "a", "circunflexo"), ("ã", "a", "til"),
    ("é", "e", "agudo"), ("ê", "e", "circunflexo"),
    ("í", "i", "agudo"),
    ("ó", "o", "agudo"), ("ô", "o", "circunflexo"), ("õ", "o", "til"),
    ("ú", "u", "agudo"), ("ü", "u", "trema"),
    ("ç", "c", "cedilha"),
    ("Á", "A", "agudo"), ("À", "A", "grave"),
    ("Â", "A", "circunflexo"), ("Ã", "A", "til"),
    ("É", "E", "agudo"), ("Ê", "E", "circunflexo"),
    ("Í", "I", "agudo"),
    ("Ó", "O", "agudo"), ("Ô", "O", "circunflexo"), ("Õ", "O", "til"),
    ("Ú", "U", "agudo"),
    ("Ç", "C", "cedilha"),
]


def sjis_de(letra: str) -> int:
    if "A" <= letra <= "Z":
        return 0x8260 + (ord(letra) - ord("A"))
    if "a" <= letra <= "z":
        return 0x8281 + (ord(letra) - ord("a"))
    raise ValueError(letra)


def extent_vertical(rows: list[str]) -> tuple[int, int]:
    primeira = ultima = None
    for y, r in enumerate(rows):
        if "#" in r:
            if primeira is None:
                primeira = y
            ultima = y
    return (0, 0) if primeira is None else (primeira, ultima)


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    header, _ = fontmod.read_font_header(rom)
    w, h = header["width"], header["height"]
    data = rom[header["data_offset"]: header["data_offset"] + header["data_size"]]
    count = header["data_size"] // (fontmod.glyph_bytes_per_row(w) * h)

    print("=" * 72)
    print("ESPACO VERTICAL DISPONIVEL EM CIMA DE CADA LETRA")
    print("=" * 72)
    print(f"  fonte: {w}x{h}, {count:,} glifos")
    print()

    folgas: dict[str, tuple[int, int, int]] = {}
    for letra in "aeiouAEIOUcC":
        idx = fontmod.sjis_to_glyph_index(rom, sjis_de(letra))
        if idx is None or idx >= count:
            print(f"      '{letra}': SEM GLIFO")
            continue
        rows = fontmod.decode_glyph(data, idx, w, h)
        topo, base = extent_vertical(rows)
        folgas[letra] = (topo, base, h - 1 - base)
        print(f"      '{letra}': ocupa linhas {topo}-{base} | "
              f"folga em cima: {topo} | embaixo: {h-1-base}")

    print()
    print("  Acentos precisam de 2-3 linhas em cima. Cedilha precisa de 3 embaixo.")

    # --- quais slots de glifo estao livres? ---
    print()
    print("=" * 72)
    print("SLOTS DE GLIFO DISPONIVEIS")
    print("=" * 72)
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
                if len(par) != 2:
                    continue
                idx = fontmod.sjis_to_glyph_index(rom, (par[0] << 8) | par[1])
                if idx is not None and idx < count:
                    usados.add(idx)
    livres = [i for i in range(count) if i not in usados]
    print(f"  glifos usados nos dialogos : {len(usados):,}")
    print(f"  slots livres para sobrescrever: {len(livres):,}")
    print(f"  precisamos de              : {len(NECESSARIAS)}")

    # --- codigos Shift-JIS livres na tabela de lookup ---
    print()
    print("=" * 72)
    print("CODIGOS SHIFT-JIS SEM GLIFO (para apontar para os novos)")
    print("=" * 72)
    vagos = []
    for lead in range(0x81, 0xA0):
        for trail in range(0x40, 0x100):
            if trail == 0x7F:
                continue
            code = (lead << 8) | trail
            if fontmod.sjis_to_glyph_index(rom, code) is None:
                vagos.append(code)
    print(f"  codigos sem glifo na faixa 0x81-0x9F: {len(vagos):,}")
    if vagos:
        print(f"  primeiros: " + ", ".join(f"0x{c:04X}" for c in vagos[:12]))

    # --- compoe e desenha uma amostra ---
    print()
    print("=" * 72)
    print("AMOSTRA COMPOSTA")
    print("=" * 72)

    def compor(base_letra: str, acento: str) -> list[str] | None:
        idx = fontmod.sjis_to_glyph_index(rom, sjis_de(base_letra))
        if idx is None or idx >= count:
            return None
        rows = fontmod.decode_glyph(data, idx, w, h)
        topo, fundo = extent_vertical(rows)
        a, b = fontmod.ink_bounds(rows)
        largura_letra = b - a + 1

        if acento == "cedilha":
            desenho = CEDILHA
            espaco = h - 1 - fundo
            if espaco < len(desenho):
                deslocar = len(desenho) - espaco
                rows = ["." * w] * 0 + rows[deslocar:] + ["." * w] * deslocar
                rows = rows[:h]
                topo, fundo = extent_vertical(rows)
            novas = list(rows)
            inicio = fundo + 1
            cx = a + (largura_letra - len(desenho[0])) // 2
            for i, linha in enumerate(desenho):
                y = inicio + i
                if y >= h:
                    break
                fila = list(novas[y])
                for j, p in enumerate(linha):
                    if p == "#" and 0 <= cx + j < w:
                        fila[cx + j] = "#"
                novas[y] = "".join(fila)
            return novas

        desenho = ACENTOS[acento]
        if topo < len(desenho):
            deslocar = len(desenho) - topo
            rows = ["." * w] * deslocar + rows[:-deslocar]
            topo, fundo = extent_vertical(rows)
            a, b = fontmod.ink_bounds(rows)
            largura_letra = b - a + 1

        novas = list(rows)
        inicio = topo - len(desenho)
        cx = a + (largura_letra - len(desenho[0])) // 2
        for i, linha in enumerate(desenho):
            y = inicio + i
            if y < 0:
                continue
            fila = list(novas[y])
            for j, p in enumerate(linha):
                if p == "#" and 0 <= cx + j < w:
                    fila[cx + j] = "#"
            novas[y] = "".join(fila)
        return novas

    for ch, base_letra, acento in NECESSARIAS[:4] + [("ç", "c", "cedilha"),
                                                     ("Á", "A", "agudo")]:
        rows = compor(base_letra, acento)
        print(f"\n  '{ch}' = '{base_letra}' + {acento}")
        if rows is None:
            print("      base sem glifo")
            continue
        for r in rows:
            print(f"      {r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
