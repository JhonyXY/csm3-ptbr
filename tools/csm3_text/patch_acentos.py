#!/usr/bin/env python3
"""Adiciona as acentuadas do portugues a fonte do jogo.

Duas alteracoes, ambas NO LUGAR (mesmo tamanho em bytes, nada desloca):

  1. 25 slots de glifo consecutivos que o jogo nao usa passam a conter as
     acentuadas, compostas a partir das letras que ja existem.
  2. 25 codigos Shift-JIS consecutivos do bloco cirilico - que decodificam em
     Python mas nao tem glifo - passam a apontar para esses slots na tabela de
     lookup lida por sub_0800348C.

O cirilico foi escolhido porque decodifica sem erro (nao quebra o round-trip do
pipeline) e o jogo nao usa nenhum deles em lugar nenhum.

    python3 patch_acentos.py            # aplica
    python3 patch_acentos.py --reverter # desfaz
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import font as fontmod
from acentos import (ACENTOS, CEDILHA, NECESSARIAS, RESPIRO, desenho_do_acento,
                     extent_vertical, sjis_de)

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"
BACKUP = ".pre-acentos"

TABELA_BAIXA = 0x0B6D624   # lookup dos leads 0x81-0x9F
SJIS_BASE = 0x8440         # inicio do bloco cirilico

INCBIN = re.compile(r'^\s*\.incbin\s+"baserom\.gba",\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+)')
LABEL = re.compile(r"^(\w+)::")


def backup(path: Path) -> None:
    b = path.with_suffix(path.suffix + BACKUP)
    if not b.exists():
        shutil.copy2(path, b)


def reverter() -> int:
    print("=" * 72)
    print("REVERTENDO AS ACENTUADAS")
    print("=" * 72)
    for path in sorted((REPO / "data").glob("*.s" + BACKUP)):
        alvo = path.with_suffix("")
        shutil.copy2(path, alvo)
        alvo.touch()   # make precisa ver mtime novo, senao usa o .o velho
        path.unlink()
        print(f"  restaurado: {alvo.relative_to(REPO)}")
    # O MAPA NAO E APAGADO DE PROPOSITO.
    #
    # encoder.py le _out/acentos_mapa.json para converter 'a com til' no codigo
    # do jogo; sem o arquivo ele cai em strip_accents() e grava "Nao" sem til,
    # em silencio. Como migrar_para_build.py (que injeta as strings) roda ANTES
    # deste script - a ordem exigida pelos backups de data1.s - apagar o mapa no
    # revert abria exatamente essa janela: as strings eram gravadas sem acento e
    # so entao o mapa reaparecia. Foi assim que os acentos sumiram da build.
    #
    # A alocacao dos slots e deterministica (depende so da baserom e da lista de
    # reservados), entao manter o mapa entre um revert e o proximo patch e
    # seguro - ele sera reescrito identico.
    print("  mapa de acentos preservado (encoder.py depende dele)")
    return 0


def compor(rom, data, w, h, count, base_letra: str, acento: str) -> list[str] | None:
    idx = fontmod.sjis_to_glyph_index(rom, sjis_de(base_letra))
    if idx is None or idx >= count:
        return None
    rows = fontmod.decode_glyph(data, idx, w, h)
    topo, fundo = extent_vertical(rows)
    a, b = fontmod.ink_bounds(rows)
    largura = b - a + 1

    if acento == "cedilha":
        desenho = CEDILHA
        espaco = h - 1 - fundo
        if espaco < len(desenho):
            deslocar = len(desenho) - espaco
            rows = rows[deslocar:] + ["." * w] * deslocar
            topo, fundo = extent_vertical(rows)
        novas = list(rows)
        inicio = fundo + 1
    else:
        desenho = desenho_do_acento(acento, base_letra)
        # O acento precisa da propria altura MAIS o respiro; senao encosta na
        # letra e os dois viram uma mancha so.
        preciso = len(desenho) + RESPIRO
        if topo < preciso:
            deslocar = preciso - topo
            rows = ["." * w] * deslocar + rows[:-deslocar]
            topo, fundo = extent_vertical(rows)
            a, b = fontmod.ink_bounds(rows)
            largura = b - a + 1
        novas = list(rows)
        inicio = topo - preciso

    cx = a + (largura - len(desenho[0])) // 2
    for i, linha in enumerate(desenho):
        y = inicio + i
        if not (0 <= y < h):
            continue
        fila = list(novas[y])
        for j, p in enumerate(linha):
            if p == "#" and 0 <= cx + j < w:
                fila[cx + j] = "#"
        novas[y] = "".join(fila)
    return novas


def rows_para_bytes(rows: list[str], w: int) -> bytes:
    out = bytearray()
    for r in rows:
        b0 = b1 = 0
        for x in range(min(8, w)):
            if r[x] == "#":
                b0 |= 0x80 >> x
        for x in range(8, w):
            if r[x] == "#":
                b1 |= 0x80 >> (x - 8)
        out += bytes((b0, b1))
    return bytes(out)


def indexar_blocos() -> list[dict]:
    blocos = []
    for path in sorted((REPO / "data").glob("*.s")):
        if path.name.startswith("ptbr"):
            continue
        label = None
        for i, linha in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
            m = LABEL.match(linha)
            if m:
                label = m.group(1)
                continue
            m = INCBIN.match(linha)
            if m:
                blocos.append({"arquivo": path, "linha": i, "rotulo": label,
                               "off": int(m.group(1), 16), "size": int(m.group(2), 16)})
    return blocos


def recortar(path: Path, linha_idx: int, bloco_off: int, bloco_size: int,
             alvo_off: int, dados: bytes, comentario: str) -> None:
    """Troca [alvo_off, alvo_off+len(dados)) dentro de um .incbin por bytes."""
    linhas = path.read_text(encoding="utf-8").splitlines()
    novas = []
    fim_bloco = bloco_off + bloco_size
    fim_alvo = alvo_off + len(dados)

    if alvo_off > bloco_off:
        novas.append(f'\t.incbin "baserom.gba", 0x{bloco_off:X}, 0x{alvo_off-bloco_off:X}')
    novas.append(f"\t@ {comentario}")
    for i in range(0, len(dados), 16):
        pedaco = dados[i:i + 16]
        novas.append("\t.byte " + ", ".join(f"0x{b:02X}" for b in pedaco))
    if fim_bloco > fim_alvo:
        novas.append(f'\t.incbin "baserom.gba", 0x{fim_alvo:X}, 0x{fim_bloco-fim_alvo:X}')

    linhas[linha_idx:linha_idx + 1] = novas
    path.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reverter", action="store_true")
    ap.add_argument("--so-mapa", action="store_true",
                    help="calcula a alocacao e grava os JSON, sem tocar em "
                         "data1.s; quebra o ciclo com migrar_para_build.py")
    args = ap.parse_args()
    if args.reverter:
        return reverter()

    rom = csm3rom.load_rom(REPO / "baserom.gba")
    header, _ = fontmod.read_font_header(rom)
    w, h = header["width"], header["height"]
    data = rom[header["data_offset"]: header["data_offset"] + header["data_size"]]
    count = header["data_size"] // (fontmod.glyph_bytes_per_row(w) * h)

    print("=" * 72)
    print("ACENTUADAS DO PORTUGUES")
    print("=" * 72)

    # --- acha 25 slots consecutivos que o jogo nao usa ---
    usados = set()
    d = json.loads((OUT / "textos_originais.json").read_text(encoding="utf-8"))
    for e in d["strings"]:
        for ch in e["jp"]:
            try:
                par = ch.encode("shift_jis")
            except UnicodeEncodeError:
                continue
            if len(par) == 2:
                idx = fontmod.sjis_to_glyph_index(rom, (par[0] << 8) | par[1])
                if idx is not None and idx < count:
                    usados.add(idx)

    # CRITICO: os glifos latinos nao aparecem no texto japones, entao entrariam
    # na lista de "livres" - e sobrescreve-los apagaria as proprias letras que a
    # traducao usa. Reserva tudo que a traducao PT-BR precisa.
    reservados = set()
    for faixa_lo, faixa_hi in ((0x824F, 0x8258),   # digitos
                               (0x8260, 0x8279),   # A-Z
                               (0x8281, 0x829A),   # a-z
                               (0x8140, 0x81FF)):  # pontuacao e simbolos
        for code in range(faixa_lo, faixa_hi + 1):
            idx = fontmod.sjis_to_glyph_index(rom, code)
            if idx is not None and idx < count:
                reservados.add(idx)
    # Os placeholders de nome (letras gregas) tambem sao intocaveis.
    for code in range(0x83BF, 0x83D7):
        idx = fontmod.sjis_to_glyph_index(rom, code)
        if idx is not None and idx < count:
            reservados.add(idx)

    print(f"  glifos reservados (latino, pontuacao, placeholders): {len(reservados)}")
    usados |= reservados

    n = len(NECESSARIAS)
    blocos = indexar_blocos()

    def cabe_num_bloco(off: int, tamanho: int):
        for b in blocos:
            if b["off"] <= off and off + tamanho <= b["off"] + b["size"]:
                return b
        return None

    # O intervalo precisa estar livre E caber dentro de UM unico .incbin -
    # recortar um bloco e simples, costurar dois seria bem mais delicado.
    inicio = None
    corrida = 0
    for i in range(count):
        corrida = corrida + 1 if i not in usados else 0
        if corrida >= n:
            cand = i - n + 1
            if cabe_num_bloco(header["data_offset"] + cand * 24, n * 24):
                inicio = cand
                break
    if inicio is None:
        print(f"  ERRO: nao achei {n} slots livres consecutivos dentro de um "
              f"unico bloco .incbin")
        return 1
    print(f"  slots de glifo: {inicio}..{inicio+n-1} ({n} consecutivos, nenhum em uso)")
    print(f"  codigos SJIS  : 0x{SJIS_BASE:04X}..0x{SJIS_BASE+n-1:04X} (bloco cirilico)")

    # --- compoe os bitmaps ---
    bitmaps = bytearray()
    mapa = {}
    for k, (ch, base_letra, acento) in enumerate(NECESSARIAS):
        rows = compor(rom, data, w, h, count, base_letra, acento)
        if rows is None:
            print(f"  ERRO: sem glifo base para '{base_letra}'")
            return 1
        bitmaps += rows_para_bytes(rows, w)
        mapa[ch] = SJIS_BASE + k

    # gerar_larguras.py precisa saber ONDE os acentos foram parar para medir o
    # glifo COMPOSTO. Sem isso ele mede o que havia no slot antes (um simbolo
    # qualquer), e o desenhador comeca a pintar na coluna errada - o acento sai
    # cortado. Gravado aqui porque so este script sabe o resultado da alocacao.
    (OUT / "acentos_slots.json").write_text(
        json.dumps({"inicio": inicio, "quantidade": n,
                    "chars": [c for c, _, _ in NECESSARIAS]}, indent=2),
        encoding="utf-8")

    # --so-mapa para aqui: grava os dois JSON e nao encosta em data1.s.
    #
    # Existe por causa de um ciclo: encoder.py precisa de acentos_mapa.json para
    # codificar as acentuadas, e quem usa o encoder e migrar_para_build.py, que
    # TEM que rodar antes deste script (os dois mexem em data1.s e cada um guarda
    # o proprio backup; inverter a ordem faz um desfazer o outro). Num clone novo
    # o mapa nao existiria a tempo e as strings sairiam sem acento, em silencio.
    if args.so_mapa:
        (OUT / "acentos_mapa.json").write_text(
            json.dumps({ch: f"0x{c:04X}" for ch, c in mapa.items()},
                       indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  mapa e slots gravados; data1.s intocado (--so-mapa)")
        return 0
    print(f"  bitmaps compostos: {len(NECESSARIAS)} ({len(bitmaps)} bytes)")

    # --- localiza os dois blocos a recortar ---
    blocos = indexar_blocos()
    off_glifos = header["data_offset"] + inicio * 24
    off_tabela = TABELA_BAIXA + ((SJIS_BASE >> 8) - 0x81) * 192 * 2 \
                 + ((SJIS_BASE & 0xFF) - 0x40) * 2

    def achar(off: int, tamanho: int):
        for b in blocos:
            if b["off"] <= off and off + tamanho <= b["off"] + b["size"]:
                return b
        return None

    b_glifos = achar(off_glifos, len(bitmaps))
    b_tabela = achar(off_tabela, n * 2)
    if not b_glifos or not b_tabela:
        print(f"  ERRO: nao achei bloco para glifos ({b_glifos}) ou tabela ({b_tabela})")
        return 1
    if b_glifos["arquivo"] == b_tabela["arquivo"] and b_glifos["linha"] == b_tabela["linha"]:
        print("  ERRO: glifos e tabela no mesmo bloco - nao tratado")
        return 1

    print(f"  glifos em {b_glifos['arquivo'].name}:{b_glifos['linha']+1} "
          f"({b_glifos['rotulo']})")
    print(f"  tabela em {b_tabela['arquivo'].name}:{b_tabela['linha']+1} "
          f"({b_tabela['rotulo']})")

    # --- aplica: primeiro o que estiver mais adiante, para nao mover o outro ---
    entradas = b"".join(struct.pack("<H", inicio + k + 1) for k in range(n))

    alvos = [
        (b_glifos, off_glifos, bytes(bitmaps), "acentuadas PT-BR (25 glifos de 24 bytes)"),
        (b_tabela, off_tabela, entradas, "lookup SJIS 0x8440+ -> acentuadas PT-BR"),
    ]
    for bloco, _, _, _ in alvos:
        backup(bloco["arquivo"])

    for bloco, off, dados, comentario in sorted(
            alvos, key=lambda x: (x[0]["arquivo"].name, -x[0]["linha"])):
        recortar(bloco["arquivo"], bloco["linha"], bloco["off"], bloco["size"],
                 off, dados, comentario)

    (OUT / "acentos_mapa.json").write_text(
        json.dumps({ch: f"0x{code:04X}" for ch, code in mapa.items()},
                   indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print("  mapa gravado em _out/acentos_mapa.json:")
    for ch, code in list(mapa.items())[:8]:
        print(f"      '{ch}' -> SJIS 0x{code:04X}")
    print(f"      ... e mais {len(mapa)-8}")
    print()
    print("  Nada mudou de tamanho: os .incbin foram recortados e a mesma")
    print("  quantidade de bytes reemitida como .byte.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
