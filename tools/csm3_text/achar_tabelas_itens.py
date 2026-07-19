#!/usr/bin/env python3
"""Procura as tabelas de nomes de item/arma/magia fora dos archives.

A pesquisa indicou ~1.184 nomes em Shift-JIS cru na ROM - materiais, armas,
magias, inimigos. Meu pipeline so cobre o archive 2 (dialogo) e as 43 strings
de sistema, entao isso e texto visivel ao jogador que eu estaria deixando de
fora.

Usa a mesma tecnica que funcionou para as strings de sistema: achar as strings,
depois achar a tabela de ponteiros que aponta para elas.
"""

from __future__ import annotations

import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
from script_text import is_sjis_pair, word_to_sjis

REPO = Path(__file__).resolve().parents[2]

# Ancoras conhecidas da pesquisa.
ANCORAS = [
    ("tipos de arma", 0x0BACBC),
    ("apelido do protagonista", 0x0BAB7C),
    ("nomes/parceiros", 0x0BD575E),
]


def ler_string(rom: bytes, pos: int, limite: int = 40) -> str | None:
    raw = bytearray()
    n = 0
    while pos + 2 <= len(rom) and n < limite:
        w = struct.unpack_from("<H", rom, pos)[0]
        if w == 0:
            break
        if not is_sjis_pair(w):
            return None
        raw += word_to_sjis(w)
        pos += 2
        n += 1
    if not raw:
        return None
    try:
        return bytes(raw).decode("shift_jis")
    except UnicodeDecodeError:
        return None


def varrer_regiao(rom: bytes, inicio: int, fim: int) -> list[tuple[int, str]]:
    """Acha strings SJIS terminadas em 0x0000 numa faixa."""
    achados = []
    pos = inicio
    while pos < fim - 2:
        w = struct.unpack_from("<H", rom, pos)[0]
        if is_sjis_pair(w):
            s = ler_string(rom, pos)
            if s and len(s) >= 2:
                achados.append((pos, s))
                pos += len(s) * 2 + 2
                continue
        pos += 2
    return achados


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")

    print("=" * 72)
    print("REGIOES DE TEXTO CRU FORA DOS ARCHIVES")
    print("=" * 72)

    for nome, ancora in ANCORAS:
        print(f"\n  --- {nome} (ancora 0x{ancora:07X}) ---")
        achados = varrer_regiao(rom, max(0, ancora - 0x40), ancora + 0x200)
        for pos, s in achados[:14]:
            print(f"      0x{pos:07X}  {s}")
        if len(achados) > 14:
            print(f"      ... e mais {len(achados)-14}")

    # --- varredura ampla da area de dados nao comprimidos ---
    print()
    print("=" * 72)
    print("VARREDURA AMPLA (0x0BA000..0x0BE000)")
    print("=" * 72)
    todas = varrer_regiao(rom, 0x0BA000, 0x0BE000)
    print(f"  strings encontradas: {len(todas):,}")
    tamanhos = Counter(len(s) for _, s in todas)
    print(f"  tamanho: min {min(tamanhos)} / max {max(tamanhos)} caracteres")

    print("\n  amostra distribuida:")
    passo = max(1, len(todas) // 25)
    for pos, s in todas[::passo][:25]:
        print(f"      0x{pos:07X}  {s}")

    # --- as strings tem tabela de ponteiros? ---
    print()
    print("=" * 72)
    print("EXISTE TABELA DE PONTEIROS PARA ELAS?")
    print("=" * 72)
    if todas:
        alvo = todas[len(todas) // 2][0]
        agulha = struct.pack("<I", 0x08000000 + alvo)
        hits = []
        p = rom.find(agulha)
        while p != -1 and len(hits) < 6:
            hits.append(p)
            p = rom.find(agulha, p + 1)
        s = todas[len(todas) // 2][1]
        print(f"  testando \"{s}\" em 0x{alvo:07X}")
        print(f"  ponteiros achados: {len(hits)}")
        for h in hits:
            print(f"      0x{h:07X}")
        if hits:
            print("\n  contexto do primeiro (procurando tabela):")
            base = hits[0]
            for off in range(max(0, base - 24), base + 28, 4):
                val = struct.unpack_from("<I", rom, off)[0]
                if 0x08000000 <= val < 0x0A000000:
                    txt = ler_string(rom, val - 0x08000000) or ""
                    marca = "  <==" if off == base else ""
                    print(f"      0x{off:07X}: 0x{val:08X}  \"{txt}\"{marca}")
        else:
            print("  Nenhum ponteiro direto: as strings devem ser acessadas por")
            print("  indice sobre um endereco base, com passo fixo.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
