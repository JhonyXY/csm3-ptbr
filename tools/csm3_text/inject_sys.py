#!/usr/bin/env python3
"""Injeta as strings de sistema (menus de save, item, loja).

Estas strings ficam cruas na ROM e sao acessadas por uma tabela de ponteiros em
0x0BC9EC8. Como o acesso e por ponteiro, a traducao NAO precisa caber no espaco
original: escrevemos no espaco livre do fim da ROM e reapontamos.

Roda DEPOIS de inject.py, reaproveitando o espaco livre que sobrou.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import encoder
from script_text import is_sjis_pair, word_to_sjis

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"

FREE_REGION_START = 0x1FBB1ED


def achar_cursor_livre(rom: bytes) -> int:
    """Acha o primeiro byte realmente livre, pulando o que ja foi escrito."""
    pos = len(rom)
    while pos > FREE_REGION_START and rom[pos - 1] == 0:
        pos -= 1
    # Alinha em 4 para os ponteiros ficarem limpos.
    return (max(pos, FREE_REGION_START) + 3) // 4 * 4


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default="csm3_ptbr.gba",
                    help="ROM de entrada; e tambem a de saida")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    dados = json.loads((OUT / "sysstrings.json").read_text(encoding="utf-8"))
    entradas = [e for e in dados["strings"] if (e.get("pt") or "").strip()]

    rom_path = REPO / args.rom
    rom = bytearray(csm3rom.load_rom(rom_path))

    print("=" * 72)
    print("INJECAO DAS STRINGS DE SISTEMA")
    print("=" * 72)
    print(f"  ROM              : {rom_path.name}")
    print(f"  strings a injetar: {len(entradas)} de {len(dados['strings'])}")

    cursor = achar_cursor_livre(bytes(rom))
    inicio = cursor
    print(f"  espaco livre a partir de 0x{cursor:07X} "
          f"({len(rom) - cursor:,} bytes)")
    print()

    # Strings identicas compartilham um unico destino, para nao desperdicar.
    ja_escritas: dict[str, int] = {}
    escritas = 0
    reapontadas = 0

    for e in entradas:
        pt = e["pt"]
        if pt in ja_escritas:
            destino = ja_escritas[pt]
        else:
            try:
                palavras = encoder.encode(pt)
            except encoder.EncodeError as exc:
                print(f"  ERRO em \"{pt}\": {exc}")
                return 1
            blob = b"".join(struct.pack("<H", w) for w in palavras)
            blob += b"\x00\x00"  # terminador
            if cursor + len(blob) > len(rom):
                print(f"  ERRO: espaco livre esgotado em \"{pt}\"")
                return 1
            if not args.dry_run:
                rom[cursor : cursor + len(blob)] = blob
            ja_escritas[pt] = cursor
            destino = cursor
            cursor += len(blob)
            cursor = (cursor + 3) // 4 * 4
            escritas += 1

        novo_ptr = 0x08000000 + destino
        if not args.dry_run:
            struct.pack_into("<I", rom, e["ponteiro"], novo_ptr)
        reapontadas += 1

    usado = cursor - inicio
    print(f"  strings distintas escritas: {escritas}")
    print(f"  ponteiros reapontados     : {reapontadas}")
    print(f"  espaco usado              : {usado:,} bytes")
    print(f"  livre restante            : {len(rom) - cursor:,} bytes")

    if args.dry_run:
        print("\n  --dry-run: nada foi escrito")
        return 0

    rom_path.write_bytes(bytes(rom))
    print(f"\n  ROM atualizada: {rom_path}")

    # --- verificacao: rele a tabela e decodifica o que os ponteiros apontam ---
    print()
    print("=" * 72)
    print("VERIFICACAO - relendo pelos ponteiros")
    print("=" * 72)
    nova = csm3rom.load_rom(rom_path)
    ok = 0
    for e in entradas:
        ptr = struct.unpack_from("<I", nova, e["ponteiro"])[0]
        pos = ptr - 0x08000000
        raw = bytearray()
        while pos + 2 <= len(nova):
            w = struct.unpack_from("<H", nova, pos)[0]
            if w == 0:
                break
            if not is_sjis_pair(w):
                break
            raw += word_to_sjis(w)
            pos += 2
        try:
            texto = bytes(raw).decode("shift_jis")
        except UnicodeDecodeError:
            texto = "(erro)"
        # converte largura total -> ascii so para exibir
        legivel = "".join(
            chr(ord(c) - 0xFEE0) if "！" <= c <= "～" else (" " if c == "　" else c)
            for c in texto
        )
        if legivel == e["pt"]:
            ok += 1
        else:
            print(f"      DIVERGE [{e['indice']}]: esperado \"{e['pt']}\", "
                  f"lido \"{legivel}\"")

    print(f"  strings conferidas: {ok}/{len(entradas)}")
    return 0 if ok == len(entradas) else 1


if __name__ == "__main__":
    raise SystemExit(main())
