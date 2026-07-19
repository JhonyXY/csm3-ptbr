#!/usr/bin/env python3
"""Le os bytes reais das opcoes do menu na ROM construida.

Decide entre duas hipoteses para o "Nao" sem til:
  (a) a string gravada e "Nao" mesmo - problema de injecao
  (b) a string e "Nao com til" mas o glifo nao desenha - problema de largura

Enderecos vindos da analise do menu de salvar:
  titulo 0x080BB164, itens 0x080BB2E4 e 0x080BB2DC
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"

ENDERECOS = {
    "titulo": 0x080BB164,
    "item 1": 0x080BB2E4,
    "item 2": 0x080BB2DC,
    "outro titulo": 0x080BB188,
}


def carregar_mapa():
    inv = {}
    caminho = OUT / "acentos_mapa.json"
    if caminho.exists():
        for ch, hexcode in json.loads(caminho.read_text(encoding="utf-8")).items():
            inv[int(hexcode, 16)] = ch
    return inv


def decodifica(codigo, acentos):
    """Traduz um codigo u16 do jogo para algo legivel."""
    if codigo in acentos:
        return acentos[codigo], "ACENTO"
    # Latino em SJIS de largura dupla
    if 0x8260 <= codigo <= 0x8279:
        return chr(ord("A") + codigo - 0x8260), ""
    if 0x8281 <= codigo <= 0x829A:
        return chr(ord("a") + codigo - 0x8281), ""
    if 0x824F <= codigo <= 0x8258:
        return chr(ord("0") + codigo - 0x824F), ""
    if codigo == 0x8148:
        return "?", ""
    if codigo == 0x8140:
        return " ", ""
    return f"<{codigo:04X}>", ""


def main() -> int:
    rom = csm3rom.load_rom(REPO / "csm3.gba")
    acentos = carregar_mapa()

    print("=" * 74)
    print("BYTES DAS STRINGS DO MENU, NA ROM CONSTRUIDA")
    print("=" * 74)
    print(f"  mapa de acentos: {len(acentos)} codigos "
          f"({min(acentos):#06x}..{max(acentos):#06x})" if acentos else "  sem mapa")

    for nome, addr in ENDERECOS.items():
        off = addr - 0x08000000
        texto = []
        marcas = []
        crus = []
        for i in range(24):
            codigo = int.from_bytes(rom[off + i * 2: off + i * 2 + 2], "little")
            if codigo == 0:
                break
            crus.append(f"{codigo:04X}")
            ch, marca = decodifica(codigo, acentos)
            texto.append(ch)
            if marca:
                marcas.append(ch)
        print()
        print(f"  {nome}  ({addr:#010x})")
        print(f"    lido    : {''.join(texto)}")
        print(f"    codigos : {' '.join(crus)}")
        if marcas:
            print(f"    ACENTOS PRESENTES: {' '.join(marcas)}")
        else:
            print("    nenhum codigo de acento nesta string")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
