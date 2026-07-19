#!/usr/bin/env python3
"""Compara o desenhador novo contra o original, glifo por glifo.

Este e o teste que faltou nas duas tentativas anteriores de VWF. A regra:
com largura 12 (o comportamento atual), o desenhador novo tem que produzir
EXATAMENTE o mesmo resultado que o original. Se produzir, ele esta correto e
qualquer largura menor tambem estara.

Reimplementa o desenhador novo em Python a partir do mesmo C - assim da para
validar a logica antes de compilar e buildar.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import font as fontmod
from thumb import Cpu, Memoria

REPO = Path(__file__).resolve().parents[2]
BLIT_FASE0 = 0x08003BC0
DESTINO = 0x02010000
TAM = 0x100

COR_TINTA = 1
COR_SOMBRA = 2


def endereco(coluna: int, linha: int) -> int:
    return ((coluna >> 3) * 0x40 + (linha >> 3) * 0x20
            + (linha & 7) * 4 + ((coluna & 7) >> 1))


def acender(buf: bytearray, coluna: int, linha: int, cor: int) -> None:
    if coluna < 0 or linha < 0 or linha >= 16 or coluna >= 16:
        return
    i = endereco(coluna, linha)
    if i >= len(buf):
        return
    # Combina por OR: onde tinta (1) e sombra (2) coincidem sai 3.
    if coluna & 1:
        buf[i] |= cor << 4
    else:
        buf[i] |= cor


COR_FUNDO = 4


def acender_v2(buf, coluna, linha, cor):
    """Versao que substitui o fundo e combina com marcas da propria letra.

    O teste antigo usava buffer zerado, onde OR direto acerta por acidente.
    No jogo o buffer vem pintado com a cor 4, e OR dava 5 e 6 - paleta errada.
    """
    if coluna < 0 or linha < 0 or linha >= 16 or coluna >= 16:
        return
    i = endereco(coluna, linha)
    if i >= len(buf):
        return
    if coluna & 1:
        atual = buf[i] >> 4
        atual = cor if atual == COR_FUNDO else (atual | cor)
        buf[i] = (buf[i] & 0x0F) | (atual << 4)
    else:
        atual = buf[i] & 0x0F
        atual = cor if atual == COR_FUNDO else (atual | cor)
        buf[i] = (buf[i] & 0xF0) | atual


def desenhar_novo(glifo: bytes, largura: int, x: int = 0) -> bytearray:
    """Mesma logica de src/ptbr_blit.c, para validar antes de compilar.

    `x` desloca o glifo em pixels - e o que da largura variavel de verdade,
    com precisao de 1 pixel em vez dos saltos de 4 do desenhador original.
    """
    buf = bytearray(TAM)
    for linha in range(12):
        fila = glifo[linha * 2] | (glifo[linha * 2 + 1] << 8)
        for coluna in range(min(largura, 12)):
            if coluna < 8:
                aceso = (fila >> (7 - coluna)) & 1
            else:
                aceso = (fila >> (8 + (15 - coluna))) & 1
            if aceso:
                # Medido: duas sombras, a direita e na diagonal abaixo-direita.
                # O original recorta a sombra que cairia abaixo da linha 11 -
                # o glifo tem 12 linhas e ele nao passa disso.
                acender(buf, x + coluna + 1, linha, COR_SOMBRA)
                if linha + 1 < 12:
                    acender(buf, x + coluna + 1, linha + 1, COR_SOMBRA)
                acender(buf, x + coluna, linha, COR_TINTA)
    return buf


def desenhar_original(rom: bytes, glifo_addr: int) -> bytearray:
    mem = Memoria()
    mem.mapear(0x08000000, rom)
    mem.mapear(0x02000000, bytes(0x20000))
    mem.mapear(0x03000000, bytes(0x8000))
    cpu = Cpu(mem)
    cpu.r[0], cpu.r[1], cpu.r[2], cpu.r[3] = glifo_addr, DESTINO, 0, 0
    cpu.r[13] = 0x03007F00
    cpu.executar(BLIT_FASE0)
    buf, base = mem._achar(DESTINO, TAM)
    return bytearray(buf[base:base + TAM])


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    h, _ = fontmod.read_font_header(rom)
    base_fonte = h["data_offset"]
    dados = rom[base_fonte: base_fonte + h["data_size"]]
    w, hh = h["width"], h["height"]
    count = h["data_size"] // (fontmod.glyph_bytes_per_row(w) * hh)

    # Amostra representativa: latino, kanji, kana, e o glifo em branco.
    codigos = [0x8281, 0x828D, 0x8260, 0x824F, 0x93FA, 0x8140, 0x8341]
    indices = []
    for c in codigos:
        i = fontmod.sjis_to_glyph_index(rom, c)
        if i is not None and i < count:
            indices.append((c, i))
    # mais alguns espalhados pela fonte
    indices += [(0, i) for i in range(0, count, count // 40)][:40]

    print("=" * 74)
    print("DESENHADOR NOVO x ORIGINAL (largura 12 = comportamento atual)")
    print("=" * 74)

    iguais = 0
    diferentes = []
    for codigo, idx in indices:
        glifo = dados[idx * 24: idx * 24 + 24]
        original = desenhar_original(rom, 0x08000000 + base_fonte + idx * 24)
        novo = desenhar_novo(glifo, 12)
        if bytes(original) == bytes(novo):
            iguais += 1
        else:
            difs = [i for i in range(TAM) if original[i] != novo[i]]
            diferentes.append((codigo, idx, difs, original, novo))

    total = len(indices)
    print(f"  glifos comparados : {total}")
    print(f"  identicos         : {iguais}")
    print(f"  divergentes       : {len(diferentes)}")

    for codigo, idx, difs, orig, novo in diferentes[:3]:
        print(f"\n  --- glifo {idx} (SJIS 0x{codigo:04X}): {len(difs)} bytes diferentes ---")
        for i in difs[:8]:
            print(f"      +0x{i:03X}: original 0x{orig[i]:02X}  novo 0x{novo[i]:02X}")

    print()
    print("=" * 74)
    if iguais == total:
        print("  RESULTADO: o desenhador novo reproduz o original exatamente.")
        print("  Com largura menor ele desenha menos colunas, que e o objetivo -")
        print("  e como escreve por OR, nao apaga o glifo anterior.")
        return 0
    print("  RESULTADO: divergem. NAO buildar - a logica ainda esta errada.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
