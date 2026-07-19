#!/usr/bin/env python3
"""O linker consegue repointar os dados deste repo?

Para o linker realocar algo, a referencia precisa ser SIMBOLICA (.4byte simbolo).
Se os ponteiros estao dentro de um .incbin, sao bytes crus e o linker nao tem o
que ajustar.

Este script responde:
  1. Onde, em data/*.s, cai o endereco da tabela de ponteiros de sistema?
  2. Quantas referencias simbolicas existem em data/ contra quantos bytes crus?
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ALVO = 0x08BC9EC8  # tabela de ponteiros das strings de sistema

INCBIN = re.compile(r'\.incbin\s+"baserom\.gba",\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+)')
LABEL = re.compile(r"^(\w+)::")


def main() -> int:
    print("=" * 72)
    print(f"ONDE CAI 0x{ALVO:08X} NO REPO?")
    print("=" * 72)

    alvo_rom = ALVO - 0x08000000
    achou = False
    for path in sorted((REPO / "data").glob("*.s")):
        label_atual = None
        for i, linha in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            m = LABEL.match(linha)
            if m:
                label_atual = m.group(1)
            m = INCBIN.search(linha)
            if not m:
                continue
            off = int(m.group(1), 16)
            size = int(m.group(2), 16)
            if off <= alvo_rom < off + size:
                print(f"\n  arquivo : data/{path.name}:{i}")
                print(f"  simbolo : {label_atual}")
                print(f"  linha   : {linha.strip()}")
                print(f"  faixa   : 0x{off:07X}..0x{off+size:07X} ({size} bytes)")
                print(f"  o alvo esta {alvo_rom - off} bytes dentro desse bloco")
                achou = True
                break
        if achou:
            break
    if not achou:
        print("  nao encontrado em nenhum .incbin")

    print()
    print("=" * 72)
    print("DATA/ E SIMBOLICO OU CRU?")
    print("=" * 72)

    total_incbin = 0
    total_bytes = 0
    total_4byte_sym = 0
    total_4byte_num = 0
    labels = 0

    for path in sorted((REPO / "data").glob("*.s")):
        texto = path.read_text(encoding="utf-8", errors="replace")
        for m in INCBIN.finditer(texto):
            total_incbin += 1
            total_bytes += int(m.group(2), 16)
        labels += len(LABEL.findall(texto))
        for m in re.finditer(r"\.4byte\s+(\S+)", texto):
            arg = m.group(1)
            if arg.startswith("0x") or arg.isdigit():
                total_4byte_num += 1
            else:
                total_4byte_sym += 1

    print(f"  diretivas .incbin        : {total_incbin:,}")
    print(f"  bytes vindos do baserom  : {total_bytes:,}")
    print(f"  rotulos (::)             : {labels:,}")
    print(f"  .4byte com SIMBOLO       : {total_4byte_sym:,}  <- o que o linker repointa")
    print(f"  .4byte com numero literal: {total_4byte_num:,}")

    print()
    print("=" * 72)
    print("O MESMO PARA asm/ (codigo)")
    print("=" * 72)
    sym = num = 0
    for path in sorted((REPO / "asm").glob("*.s")):
        texto = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"\.4byte\s+(\S+)", texto):
            arg = m.group(1)
            if arg.startswith("0x") or arg.isdigit():
                num += 1
            else:
                sym += 1
    print(f"  .4byte com SIMBOLO       : {sym:,}")
    print(f"  .4byte com numero literal: {num:,}")

    print()
    print("=" * 72)
    print("TAMANHO DA ROM QUE O BUILD PRODUZ")
    print("=" * 72)
    rom = REPO / "csm3.gba"
    if rom.exists():
        n = rom.stat().st_size
        print(f"  csm3.gba : {n:,} bytes = {n/1048576:.2f} MiB")
        print(f"  maximo do GBA (0x2000000) : 33,554,432 bytes = 32 MiB")
        print(f"  folga    : {33554432 - n:,} bytes")
    else:
        print("  csm3.gba nao existe (rode o build)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
