#!/usr/bin/env python3
"""Verifica a ROM produzida pelo make (csm3.gba) contra o baserom.

Confere:
  - os 43 ponteiros agora apontam para a area nova, resolvida pelo linker
  - as strings leem de volta como portugues
  - NADA fora dos ponteiros e da area nova mudou de endereco
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
from script_text import is_sjis_pair, word_to_sjis

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"


def ler_string(rom: bytes, pos: int) -> str:
    raw = bytearray()
    while pos + 2 <= len(rom):
        w = struct.unpack_from("<H", rom, pos)[0]
        if w == 0 or not is_sjis_pair(w):
            break
        raw += word_to_sjis(w)
        pos += 2
    try:
        t = bytes(raw).decode("shift_jis")
    except UnicodeDecodeError:
        return "(erro)"
    return "".join(
        chr(ord(c) - 0xFEE0) if "！" <= c <= "～" else (" " if c == "　" else c)
        for c in t
    )


def main() -> int:
    base = csm3rom.load_rom(REPO / "baserom.gba")
    nova = csm3rom.load_rom(REPO / "csm3.gba")
    dados = json.loads((OUT / "sysstrings.json").read_text(encoding="utf-8"))

    print("=" * 72)
    print("PONTEIROS RESOLVIDOS PELO LINKER")
    print("=" * 72)
    ok = 0
    novos_alvos = []
    for e in dados["strings"][:12]:
        antigo = struct.unpack_from("<I", base, e["ponteiro"])[0]
        novo = struct.unpack_from("<I", nova, e["ponteiro"])[0]
        texto = ler_string(nova, novo - 0x08000000)
        marca = "OK" if texto == e["pt"] else f"DIVERGE (lido: {texto!r})"
        print(f"  [{e['indice']:2d}] 0x{antigo:08X} -> 0x{novo:08X}  "
              f"\"{texto}\"  {marca}")

    for e in dados["strings"]:
        novo = struct.unpack_from("<I", nova, e["ponteiro"])[0]
        novos_alvos.append(novo - 0x08000000)
        if ler_string(nova, novo - 0x08000000) == e["pt"]:
            ok += 1
    print(f"\n  strings conferidas: {ok}/{len(dados['strings'])}")
    print(f"  area nova: 0x{min(novos_alvos):07X}..0x{max(novos_alvos):07X}")

    print()
    print("=" * 72)
    print("O QUE MUDOU NA ROM")
    print("=" * 72)
    faixas = []
    inicio = None
    for i in range(len(base)):
        if base[i] != nova[i]:
            if inicio is None:
                inicio = i
        elif inicio is not None:
            faixas.append((inicio, i))
            inicio = None
    if inicio is not None:
        faixas.append((inicio, len(base)))

    fundidas = []
    for f in faixas:
        if fundidas and f[0] - fundidas[-1][1] <= 64:
            fundidas[-1] = (fundidas[-1][0], f[1])
        else:
            fundidas.append(f)

    tabela_ini = min(e["ponteiro"] for e in dados["strings"])
    tabela_fim = max(e["ponteiro"] for e in dados["strings"]) + 4
    area_ini = min(novos_alvos)

    total = 0
    inesperado = 0
    for s, f in fundidas:
        n = f - s
        total += n
        if tabela_ini <= s < tabela_fim:
            o_que = "tabela de ponteiros (agora simbolica)"
        elif s >= area_ini - 64:
            o_que = "area nova: data/ptbr.o no fim da secao rom"
        else:
            o_que = "!!! INESPERADO"
            inesperado += 1
        print(f"  0x{s:07X}..0x{f:07X}  {n:6,d} bytes  {o_que}")

    print(f"\n  bytes alterados: {total:,} de {len(base):,} "
          f"({100*total/len(base):.4f}%)")

    print()
    print("=" * 72)
    if ok == len(dados["strings"]) and inesperado == 0:
        print("RESULTADO: build integrado funcionando.")
        print("  O linker resolveu os enderecos; nada existente deslocou.")
        return 0
    print("RESULTADO: algo fora do esperado.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
