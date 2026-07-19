#!/usr/bin/env python3
"""Desloca os glifos latinos para a esquerda, removendo a margem em branco.

E a correcao que a simulacao provou: com a tinta comecando na coluna 0, o avanco
variavel corresponde ao que foi de fato desenhado e nada se sobrepoe. Sem isso,
o glifo seguinte apaga 14% da tinta do anterior.

Reescreve os bitmaps NO LUGAR (mesmo numero de bytes) usando a mesma tecnica das
acentuadas: recorta o .incbin e reemite como .byte.

    python3 deslocar_glifos.py            # aplica
    python3 deslocar_glifos.py --reverter # desfaz
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import font as fontmod
from patch_acentos import (BACKUP, indexar_blocos, recortar, rows_para_bytes)

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"

# Faixas Shift-JIS que a traducao usa. Kanji e kana ficam como estao - eles
# ocupam a celula inteira e nao tem margem para remover.
FAIXAS = [
    ("digitos", 0x824F, 0x8258),
    ("maiusculas", 0x8260, 0x8279),
    ("minusculas", 0x8281, 0x829A),
    ("pontuacao", 0x8140, 0x8197),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reverter", action="store_true")
    args = ap.parse_args()

    data1 = REPO / "data" / "data1.s"
    if args.reverter:
        b = data1.with_suffix(data1.suffix + BACKUP)
        if b.exists():
            shutil.copy2(b, data1)
            data1.touch()
            b.unlink()
            print("  restaurado: data/data1.s")
        else:
            print("  sem backup")
        return 0

    rom = csm3rom.load_rom(REPO / "baserom.gba")
    h, _ = fontmod.read_font_header(rom)
    w, hh = h["width"], h["height"]
    data = rom[h["data_offset"]: h["data_offset"] + h["data_size"]]
    count = h["data_size"] // (fontmod.glyph_bytes_per_row(w) * hh)

    print("=" * 72)
    print("DESLOCAMENTO DOS GLIFOS LATINOS")
    print("=" * 72)

    # Coleta os glifos a deslocar e quanto cada um desloca.
    alvos: dict[int, list[str]] = {}
    total_margem = 0
    for nome, lo, hi in FAIXAS:
        n = 0
        for code in range(lo, hi + 1):
            idx = fontmod.sjis_to_glyph_index(rom, code)
            if idx is None or idx >= count or idx in alvos:
                continue
            rows = fontmod.decode_glyph(data, idx, w, hh)
            if not any("#" in r for r in rows):
                continue
            a, _ = fontmod.ink_bounds(rows)
            if a == 0:
                continue
            alvos[idx] = [r[a:] + "." * a for r in rows]
            total_margem += a
            n += 1
        print(f"  {nome:12s}: {n} glifos deslocados")

    if not alvos:
        print("  nada a fazer")
        return 0

    media = total_margem / len(alvos)
    print(f"\n  total: {len(alvos)} glifos, margem media de {media:.1f}px removida")

    # Os glifos precisam ser contiguos para um recorte so. Como estao espalhados,
    # agrupa em faixas contiguas e recorta cada uma.
    indices = sorted(alvos)
    grupos: list[list[int]] = []
    for i in indices:
        if grupos and i == grupos[-1][-1] + 1:
            grupos[-1].append(i)
        else:
            grupos.append([i])
    print(f"  faixas contiguas a recortar: {len(grupos)}")

    blocos = indexar_blocos()

    def bloco_de(off: int, tamanho: int):
        for b in blocos:
            if b["off"] <= off and off + tamanho <= b["off"] + b["size"]:
                return b
        return None

    # Agrupa por BLOCO .incbin. Duas faixas no mesmo bloco tem que sair num
    # unico recorte - aplicar dois recortes no mesmo bloco usaria indice de
    # linha desatualizado no segundo e corromperia o arquivo (foi o que
    # aconteceu na primeira tentativa: 11 MB deslocados).
    por_bloco: dict[tuple, list[list[int]]] = {}
    for g in grupos:
        off = h["data_offset"] + g[0] * 24
        tam = len(g) * 24
        b = bloco_de(off, tam)
        if b is None:
            print(f"  ERRO: faixa {g[0]}-{g[-1]} atravessa blocos .incbin")
            return 1
        chave = (b["arquivo"], b["linha"], b["off"], b["size"])
        por_bloco.setdefault(chave, []).append(g)

    print(f"  blocos .incbin envolvidos  : {len(por_bloco)}")

    bkp = data1.with_suffix(data1.suffix + BACKUP)
    if not bkp.exists():
        shutil.copy2(data1, bkp)

    # Um recorte por bloco, do fim do arquivo para o inicio.
    for (arquivo, linha, b_off, b_size), faixas in sorted(
            por_bloco.items(), key=lambda kv: -kv[0][1]):
        # Reemite o bloco inteiro: .incbin nos trechos intocados, .byte nos
        # glifos deslocados. Assim um unico recorte cobre todas as faixas.
        pedacos = []
        cursor = b_off
        for g in sorted(faixas, key=lambda x: x[0]):
            off = h["data_offset"] + g[0] * 24
            tam = len(g) * 24
            if off > cursor:
                pedacos.append(("incbin", cursor, off - cursor))
            pedacos.append(("bytes",
                            b"".join(rows_para_bytes(alvos[i], w) for i in g),
                            f"glifos {g[0]}-{g[-1]} deslocados"))
            cursor = off + tam
        if b_off + b_size > cursor:
            pedacos.append(("incbin", cursor, b_off + b_size - cursor))

        linhas_novas = []
        for p in pedacos:
            if p[0] == "incbin":
                linhas_novas.append(f'\t.incbin "baserom.gba", 0x{p[1]:X}, 0x{p[2]:X}')
            else:
                linhas_novas.append(f"\t@ {p[2]}")
                dados = p[1]
                for i in range(0, len(dados), 16):
                    bloco_b = dados[i:i + 16]
                    linhas_novas.append("\t.byte " + ", ".join(f"0x{x:02X}" for x in bloco_b))

        conteudo = arquivo.read_text(encoding="utf-8").splitlines()
        conteudo[linha:linha + 1] = linhas_novas
        arquivo.write_text("\n".join(conteudo) + "\n", encoding="utf-8")

    print(f"\n  {len(por_bloco)} recortes aplicados em data/data1.s")
    print("  Mesmo numero de bytes: nada deslocou de endereco.")
    print("\n  Agora rode gerar_larguras.py de novo - a tabela precisa refletir")
    print("  a tinta ja deslocada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
