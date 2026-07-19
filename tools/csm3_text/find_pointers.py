#!/usr/bin/env python3
"""Procura ponteiros para um endereco na ROM.

Se as strings de sistema forem referenciadas por uma tabela de ponteiros, da
para realoca-las para o espaco livre e so reescrever o ponteiro - sem a
limitacao de caber no espaco original.

Uso:
    python3 find_pointers.py 0xBB164
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom

REPO = Path(__file__).resolve().parents[2]


def main() -> int:
    alvo_rom = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0xBB164
    alvo_gba = 0x08000000 + alvo_rom

    rom = csm3rom.load_rom(REPO / "baserom.gba")
    agulha = struct.pack("<I", alvo_gba)

    print("=" * 72)
    print(f"PONTEIROS PARA 0x{alvo_gba:08X} (ROM 0x{alvo_rom:07X})")
    print("=" * 72)

    hits = []
    pos = rom.find(agulha)
    while pos != -1:
        hits.append(pos)
        pos = rom.find(agulha, pos + 1)

    print(f"\n  ocorrencias: {len(hits)}")
    for pos in hits[:20]:
        print(f"      0x{pos:07X}  (GBA 0x{0x08000000+pos:08X})")

    if not hits:
        print("\n  Nenhum ponteiro direto. As strings provavelmente sao acessadas")
        print("  por indice sobre um endereco base, nao por ponteiro individual.")
        return 0

    # Se houver ponteiro, checa se ele faz parte de uma tabela: os vizinhos
    # tambem devem ser ponteiros para a mesma regiao.
    print("\n  --- contexto do primeiro ponteiro (procurando uma tabela) ---")
    p = hits[0]
    inicio = max(0, p - 0x40)
    for off in range(inicio, min(len(rom), p + 0x44), 4):
        val = struct.unpack_from("<I", rom, off)[0]
        marca = "  <== o alvo" if off == p else ""
        eh_ptr = 0x08000000 <= val < 0x0A000000
        tipo = "ponteiro" if eh_ptr else "        "
        if eh_ptr:
            destino = val - 0x08000000
            # decodifica o inicio da string apontada, se parecer texto
            amostra = ""
            try:
                raw = bytearray()
                q = destino
                for _ in range(12):
                    w = struct.unpack_from("<H", rom, q)[0]
                    if w == 0:
                        break
                    raw += bytes((w & 0xFF, w >> 8))
                    q += 2
                amostra = bytes(raw).decode("shift_jis")
            except (UnicodeDecodeError, struct.error):
                amostra = ""
            print(f"      0x{off:07X}: 0x{val:08X}  {tipo}  \"{amostra}\"{marca}")
        else:
            print(f"      0x{off:07X}: 0x{val:08X}  {tipo}{marca}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
