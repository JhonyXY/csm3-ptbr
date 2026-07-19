#!/usr/bin/env python3
"""O avanço menor que 12px faz um glifo apagar o anterior?

O blitter ESCREVE a celula de 12px inteira (nao faz OR). Com avanco de 4 ou 8px,
o glifo seguinte cobre a cauda do anterior. A pergunta e se essa cauda tem tinta.

Se a tinta de cada glifo sempre couber DENTRO do proprio avanco, a sobreposicao
so atinge colunas vazias e nao ha problema - da para fazer VWF so removendo a
limpeza, sem reescrever o blitter para fazer OR.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import font as fontmod
from acentos import sjis_de

REPO = Path(__file__).resolve().parents[2]
UNIDADE = 4
RESPIRO = 1


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    h, _ = fontmod.read_font_header(rom)
    w, hh = h["width"], h["height"]
    data = rom[h["data_offset"]: h["data_offset"] + h["data_size"]]
    count = h["data_size"] // (fontmod.glyph_bytes_per_row(w) * hh)

    print("=" * 72)
    print("A TINTA CABE DENTRO DO PROPRIO AVANCO?")
    print("=" * 72)
    print(f"  regra do avanco: (tinta + {RESPIRO}) arredondado para cima em {UNIDADE}px")
    print()

    problemas = []
    verificados = 0
    faixas = [("digitos", 0x824F, 0x8258), ("A-Z", 0x8260, 0x8279),
              ("a-z", 0x8281, 0x829A)]

    for nome, lo, hi in faixas:
        piores = []
        for code in range(lo, hi + 1):
            idx = fontmod.sjis_to_glyph_index(rom, code)
            if idx is None or idx >= count:
                continue
            rows = fontmod.decode_glyph(data, idx, w, hh)
            if not any("#" in r for r in rows):
                continue
            a, b = fontmod.ink_bounds(rows)
            tinta = b - a + 1
            unidades = max(1, min(3, (tinta + RESPIRO + UNIDADE - 1) // UNIDADE))
            avanco = unidades * UNIDADE
            verificados += 1
            # A tinta comeca na coluna 'a' e termina em 'b'. O proximo glifo
            # comeca em 'avanco'. Se b >= avanco, ele apaga tinta.
            if b >= avanco:
                ch = bytes((code >> 8, code & 0xFF)).decode("shift_jis")
                problemas.append((ch, a, b, avanco))
                piores.append(f"'{ch}' tinta {a}-{b} vs avanco {avanco}")
        print(f"  {nome:8s}: {len(piores)} problema(s)")
        for p in piores[:6]:
            print(f"      {p}")

    print()
    print("=" * 72)
    print("VEREDITO")
    print("=" * 72)
    print(f"  glifos latinos verificados: {verificados}")
    print(f"  com tinta alem do avanco  : {len(problemas)}")
    if not problemas:
        print()
        print("  Nenhum. A sobreposicao so atinge colunas VAZIAS, entao basta")
        print("  remover a limpeza do blitter - nao preciso reescrever os")
        print("  ~400 str para fazer OR.")
    else:
        print()
        print("  Alguns glifos tem tinta na regiao sobreposta. Ou aumento o")
        print("  avanco desses, ou o blitter precisa fazer OR de verdade.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
