#!/usr/bin/env python3
"""Executa o blitter de verdade e mede o que ele escreve.

Ate agora eu deduzi o comportamento lendo assembly - e errei duas vezes. Aqui o
blitter roda no interpretador thumb, com a ROM real como memoria de codigo, e
cada escrita e registrada. O que sair daqui e medicao.

Perguntas que preciso responder:
  1. Quantos bytes ele escreve, e em que faixa a partir do destino?
  2. A limpeza inicial cobre quanto?
  3. Ele escreve zeros nas colunas sem tinta, ou preserva o que estava la?
"""

from __future__ import annotations

import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import font as fontmod
from thumb import Cpu, Memoria, ThumbError

REPO = Path(__file__).resolve().parents[2]

BLIT_FASE0 = 0x08003BC0
BLIT_FASE4 = 0x08003EB8
DESTINO = 0x02010000        # area de trabalho falsa, so para observar
TAM_DESTINO = 0x400


def rodar(rom: bytes, glifo_addr: int, fase: int, r2: int = 0, r3: int = 0,
          preencher: int = 0x00) -> tuple[Memoria, Cpu]:
    mem = Memoria()
    mem.mapear(0x08000000, rom)
    mem.mapear(DESTINO, bytes([preencher]) * TAM_DESTINO)
    mem.mapear(0x03000000, bytes(0x8000))          # IWRAM
    mem.mapear(0x02000000, bytes(0x10000))         # EWRAM baixa
    pilha = 0x03007F00
    cpu = Cpu(mem)
    cpu.r[0] = glifo_addr
    cpu.r[1] = DESTINO
    cpu.r[2] = r2
    cpu.r[3] = r3
    cpu.r[13] = pilha
    cpu.executar(fase)
    return mem, cpu


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    h, _ = fontmod.read_font_header(rom)
    w, hh = h["width"], h["height"]
    dados_fonte = rom[h["data_offset"]: h["data_offset"] + h["data_size"]]
    count = h["data_size"] // (fontmod.glyph_bytes_per_row(w) * hh)

    # Usa o 'a' minusculo: tinta estreita, e o caso que mais importa para VWF.
    idx = fontmod.sjis_to_glyph_index(rom, 0x8281)
    glifo_addr = 0x08000000 + h["data_offset"] + idx * 24
    rows = fontmod.decode_glyph(dados_fonte, idx, w, hh)
    a, b = fontmod.ink_bounds(rows)

    print("=" * 74)
    print("EXECUCAO REAL DO BLITTER (interpretador thumb)")
    print("=" * 74)
    print(f"  glifo    : 'a' (indice {idx}, endereco 0x{glifo_addr:08X})")
    print(f"  tinta    : colunas {a}..{b} ({b-a+1}px de largura)")
    print(f"  destino  : 0x{DESTINO:08X}")

    for nome, fase in (("fase 0 (sub_08003BC0)", BLIT_FASE0),
                       ("fase 4 (sub_08003EB8)", BLIT_FASE4)):
        print(f"\n  --- {nome} ---")
        try:
            mem, cpu = rodar(rom, glifo_addr, fase)
        except ThumbError as exc:
            print(f"      ERRO: {exc}")
            continue

        escritas = [(e, t, v) for e, t, v in mem.escritas
                    if DESTINO <= e < DESTINO + TAM_DESTINO]
        if not escritas:
            print("      nenhuma escrita no destino")
            continue

        menor = min(e for e, _, _ in escritas) - DESTINO
        maior = max(e + t for e, t, _ in escritas) - DESTINO
        total = sum(t for _, t, _ in escritas)
        print(f"      instrucoes executadas : {cpu.passos}")
        print(f"      escritas no destino   : {len(escritas)}")
        print(f"      faixa tocada          : +0x{menor:03X} .. +0x{maior:03X} "
              f"({maior-menor} bytes)")
        print(f"      bytes escritos        : {total}")

        # A 8 bytes por coluna de pixel, quantos pixels essa faixa cobre?
        print(f"      em pixels (8 B/coluna): {menor//8} .. {maior//8} "
              f"= {(maior-menor)//8}px de largura")

        zeros = sum(1 for _, _, v in escritas if v == 0)
        print(f"      escritas com valor 0  : {zeros} de {len(escritas)}")

    # --- a pergunta que decide o VWF -------------------------------------
    print()
    print("=" * 74)
    print("O BLITTER APAGA O QUE JA ESTAVA NO DESTINO?")
    print("=" * 74)
    mem, _ = rodar(rom, glifo_addr, BLIT_FASE0, preencher=0xFF)
    buf = mem._achar(DESTINO, TAM_DESTINO)[0]
    intactos = [i for i in range(0x100) if buf[i] == 0xFF]
    apagados = [i for i in range(0x100) if buf[i] != 0xFF]
    print(f"  destino pre-preenchido com 0xFF, nos primeiros 256 bytes:")
    print(f"      bytes intactos : {len(intactos)}")
    print(f"      bytes alterados: {len(apagados)}")
    if apagados:
        print(f"      faixa alterada : +0x{min(apagados):03X} .. +0x{max(apagados):03X}")
        print(f"      = pixels {min(apagados)//8} .. {max(apagados)//8}")
    print()
    print("  Se a faixa alterada passar de 12px, o avanco menor faz o glifo")
    print("  seguinte apagar o anterior - e essa e a raiz do bug do VWF.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
