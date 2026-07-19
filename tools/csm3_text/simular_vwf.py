#!/usr/bin/env python3
"""Simula o que o VWF produziria na tela, ANTES de mexer no assembly.

Da ultima vez eu afirmei que a limpeza de 12px dentro do blitter era a causa da
tela corrompida - mas afirmei sem provar. Este simulador reproduz o
comportamento real do blitter (escreve a celula de 12px, limpando 16px) e mostra
o resultado de cada estrategia. Assim eu vejo o defeito aqui, nao no emulador.

Estrategias comparadas:
  A  avanco variavel, glifos como estao (o que eu tentei e quebrou)
  B  avanco variavel, glifos deslocados para a esquerda (sem margem)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import font as fontmod

REPO = Path(__file__).resolve().parents[2]
LARGURA_TELA = 130
UNIDADE = 4
RESPIRO = 1


def glifo_de(rom, data, count, w, h, ch: str):
    if "A" <= ch <= "Z":
        code = 0x8260 + (ord(ch) - ord("A"))
    elif "a" <= ch <= "z":
        code = 0x8281 + (ord(ch) - ord("a"))
    elif ch == " ":
        code = 0x8140
    elif ch == "?":
        code = 0x8148
    else:
        return None
    idx = fontmod.sjis_to_glyph_index(rom, code)
    if idx is None or idx >= count:
        return None
    return fontmod.decode_glyph(data, idx, w, h)


def deslocar_esquerda(rows: list[str], w: int) -> list[str]:
    """Remove a margem esquerda: a tinta passa a comecar na coluna 0."""
    a, _ = fontmod.ink_bounds(rows)
    if a == 0 or not any("#" in r for r in rows):
        return rows
    return [r[a:] + "." * a for r in rows]


def avanco_de(rows: list[str]) -> int:
    if not any("#" in r for r in rows):
        return UNIDADE
    a, b = fontmod.ink_bounds(rows)
    tinta = b - a + 1
    unidades = max(1, min(3, (tinta + RESPIRO + UNIDADE - 1) // UNIDADE))
    return unidades * UNIDADE


def render(glifos, w, h, deslocar: bool, limpa: bool = True,
           faz_or: bool = False) -> list[str]:
    """Reproduz o blitter.

    limpa   = o blitter limpa 16px antes de desenhar (comportamento atual)
    faz_or  = escreve com OR em vez de sobrescrever (exigiria reescrever ~400
              instrucoes str do blitter)
    """
    tela = [["."] * LARGURA_TELA for _ in range(h)]
    x = 0
    for rows in glifos:
        if rows is None:
            continue
        usar = deslocar_esquerda(rows, w) if deslocar else rows
        if limpa:
            for y in range(h):
                for dx in range(16):
                    if x + dx < LARGURA_TELA:
                        tela[y][x + dx] = "."
        for y in range(h):
            for dx in range(w):
                if x + dx < LARGURA_TELA:
                    if faz_or:
                        if usar[y][dx] == "#":
                            tela[y][x + dx] = "#"
                    else:
                        tela[y][x + dx] = usar[y][dx]
        x += avanco_de(usar)
    return ["".join(l).rstrip(".") for l in tela]


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    h, _ = fontmod.read_font_header(rom)
    w, hh = h["width"], h["height"]
    data = rom[h["data_offset"]: h["data_offset"] + h["data_size"]]
    count = h["data_size"] // (fontmod.glyph_bytes_per_row(w) * hh)

    frase = "Salvar?"
    glifos = [glifo_de(rom, data, count, w, hh, c) for c in frase]

    print("=" * 74)
    print(f"SIMULACAO DO VWF - \"{frase}\"")
    print("=" * 74)

    print("\n  --- hoje: avanco fixo de 12px (referencia) ---")
    tela = [["."] * LARGURA_TELA for _ in range(hh)]
    x = 0
    for rows in glifos:
        if rows:
            for y in range(hh):
                for dx in range(w):
                    if x + dx < LARGURA_TELA:
                        tela[y][x + dx] = rows[y][dx]
        x += 12
    for l in tela:
        print("      " + "".join(l).rstrip("."))
    print(f"      largura: {x}px")

    print("\n  --- A: avanco variavel, glifos como estao ---")
    for l in render(glifos, w, hh, deslocar=False):
        print("      " + l)
    largura_a = sum(avanco_de(g) for g in glifos if g)
    print(f"      largura: {largura_a}px")

    print("\n  --- B: avanco variavel + glifos deslocados para a esquerda ---")
    for l in render(glifos, w, hh, deslocar=True):
        print("      " + l)
    largura_b = sum(avanco_de(deslocar_esquerda(g, w)) for g in glifos if g)
    print(f"      largura: {largura_b}px")

    print("\n  --- C: deslocado + SEM a limpeza do blitter ---")
    print("      (o que eu conseguiria so removendo os stm iniciais)")
    for l in render(glifos, w, hh, deslocar=True, limpa=False):
        print("      " + l)

    print("\n  --- D: deslocado + sem limpeza + blitter com OR ---")
    print("      (exige reescrever os ~400 str do blitter)")
    for l in render(glifos, w, hh, deslocar=True, limpa=False, faz_or=True):
        print("      " + l)

    # --- medicao objetiva: quanta tinta cada estrategia preserva ---
    # Contar pixels e mais confiavel que ler ASCII - foi lendo a olho que eu
    # me enganei sobre a causa da falha da primeira vez.
    esperado = 0
    for g in glifos:
        if g:
            esperado += sum(r.count("#") for r in g)

    print()
    print("=" * 74)
    print("TINTA PRESERVADA (pixels acesos)")
    print("=" * 74)
    print(f"  soma dos glifos isolados (o ideal): {esperado}")
    print()

    casos = [
        ("A  variavel, sem deslocar, com limpeza", dict(deslocar=False, limpa=True)),
        ("B  variavel, deslocado, com limpeza   ", dict(deslocar=True, limpa=True)),
        ("C  variavel, deslocado, sem limpeza   ", dict(deslocar=True, limpa=False)),
        ("D  C + blitter com OR                 ", dict(deslocar=True, limpa=False,
                                                        faz_or=True)),
    ]
    for nome, kw in casos:
        linhas = render(glifos, w, hh, **kw)
        tinta = sum(l.count("#") for l in linhas)
        perda = esperado - tinta
        estado = "INTACTO" if perda <= 0 else f"perdeu {perda} px ({100*perda/esperado:.0f}%)"
        print(f"  {nome}: {tinta:4d} px   {estado}")

    print()
    print("  A estrategia sem perda e a que funciona - e o custo em assembly")
    print("  esta no nome de cada uma.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
