#!/usr/bin/env python3
"""Acha TODAS as tabelas de ponteiros para texto na ROM.

O archive 2 tem o dialogo, mas o resto do texto que o jogador ve - menus, nomes
de item, nomes de arma, mensagens de sistema - fica cru na ROM, referenciado por
tabelas de ponteiros. Achei uma dessas por acaso (as 43 strings de sistema);
este script acha todas de forma sistematica.

Criterio: N ponteiros GBA consecutivos, alinhados em 4 bytes, todos apontando
para strings Shift-JIS validas terminadas em 0x0000.
"""

from __future__ import annotations

import json
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
from script_text import is_sjis_pair, word_to_sjis

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"

MIN_ENTRADAS = 6      # tabelas menores dao muito falso positivo
MAX_CHARS = 40        # string de UI nao passa disso


def ler_string(rom: bytes, pos: int) -> str | None:
    if pos < 0 or pos + 2 > len(rom):
        return None
    raw = bytearray()
    n = 0
    while pos + 2 <= len(rom) and n < MAX_CHARS:
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


def main() -> int:
    rom = csm3rom.load_rom(REPO / "baserom.gba")
    n = len(rom)

    # So faz sentido varrer a area de dados nao comprimidos: os archives sao
    # LZ77 e nao tem ponteiro legivel dentro.
    inicio, fim = 0x0B0000, csm3rom.ARCHIVE_OFFSETS[3]
    print("=" * 72)
    print("VARREDURA DE TABELAS DE PONTEIROS PARA TEXTO")
    print("=" * 72)
    print(f"  faixa: 0x{inicio:07X}..0x{fim:07X} ({(fim-inicio)/1024:.0f} KB)")
    print(f"  criterio: >= {MIN_ENTRADAS} ponteiros consecutivos para SJIS valido")

    cache: dict[int, str | None] = {}

    def texto_de(ptr: int) -> str | None:
        if not (0x08000000 <= ptr < 0x0A000000):
            return None
        alvo = ptr - 0x08000000
        if alvo >= n:
            return None
        if alvo not in cache:
            cache[alvo] = ler_string(rom, alvo)
        return cache[alvo]

    tabelas = []
    off = inicio
    while off < fim - 4:
        s = texto_de(struct.unpack_from("<I", rom, off)[0])
        if s is None or len(s) < 1:
            off += 4
            continue

        # achou um candidato: estende enquanto os vizinhos tambem forem validos
        entradas = []
        p = off
        while p < fim - 4:
            t = texto_de(struct.unpack_from("<I", rom, p)[0])
            if t is None or not t:
                break
            entradas.append((p, struct.unpack_from("<I", rom, p)[0], t))
            p += 4

        if len(entradas) >= MIN_ENTRADAS:
            tabelas.append({
                "inicio": off,
                "entradas": len(entradas),
                "amostra": [e[2] for e in entradas[:5]],
                "todas": entradas,
            })
            off = p
        else:
            off += 4

    print(f"\n  tabelas encontradas: {len(tabelas)}")
    total_strings = sum(t["entradas"] for t in tabelas)
    print(f"  strings referenciadas: {total_strings:,}")

    print()
    print("-" * 72)
    print("TABELAS (ordenadas por tamanho)")
    print("-" * 72)
    for t in sorted(tabelas, key=lambda x: -x["entradas"])[:24]:
        amostra = " | ".join(t["amostra"][:4])
        print(f"\n  0x{t['inicio']:07X}  {t['entradas']:4d} entradas")
        print(f"      {amostra[:96]}")

    # --- separa o que o jogador VE do que e interno ---
    import re
    # Retratos/sprites: nome de personagem seguido de numero (リッチバーン０１).
    RETRATO = re.compile(r"^[ァ-ヶー一-鿿]+[０-９]{1,2}(?:　[０-９]{1,2})?$")
    # Grade de kana da tela de nome: nao e texto, e o teclado. Reconhece pelo
    # uso de espaco de largura total como SEPARADOR entre grupos de kana - uma
    # frase normal em kana nao tem esse padrao.
    GRADE_KANA = re.compile(r"^[ぁ-んァ-ヶー]+(?:　+[ぁ-んァ-ヶー]+){2,}$")

    distintas = {}
    internas = {}
    for t in tabelas:
        for pos, ptr, txt in t["todas"]:
            off = ptr - 0x08000000
            if RETRATO.match(txt) or GRADE_KANA.match(txt):
                internas.setdefault(off, txt)
            else:
                distintas.setdefault(off, txt)

    print()
    print("-" * 72)
    print("CLASSIFICACAO")
    print("-" * 72)
    print(f"  interface (o jogador ve) : {len(distintas):,}")
    print(f"  interno (retratos, grade): {len(internas):,}")
    print("  exemplos de interno:")
    for off, txt in list(internas.items())[:4]:
        print(f"      {txt}")

    print()
    print("=" * 72)
    print("RESUMO")
    print("=" * 72)
    print(f"  strings distintas: {len(distintas):,}")
    chars = sum(len(s) for s in distintas.values())
    print(f"  caracteres japoneses: {chars:,}")
    tam = Counter(len(s) for s in distintas.values())
    print(f"  tamanho: min {min(tam)} / mediana "
          f"{sorted(len(s) for s in distintas.values())[len(distintas)//2]} "
          f"/ max {max(tam)}")

    payload = {
        "_meta": {
            "origem": "tabelas de ponteiros na area nao comprimida da ROM",
            "tabelas": len(tabelas),
            "instrucoes": [
                "Preencha 'pt'. Estas sao strings de INTERFACE: menus, nomes de",
                "item e arma, mensagens de sistema. Precisam ser CURTAS - varias",
                "aparecem em caixas estreitas de menu.",
                "Mantenha o comprimento proximo do original quando possivel.",
            ],
        },
        "tabelas": [
            {"endereco": f"0x{t['inicio']:07X}", "entradas": t["entradas"],
             "amostra": t["amostra"]}
            for t in sorted(tabelas, key=lambda x: -x["entradas"])
        ],
        "strings": [
            {"offset": off, "ponteiros": [
                f"0x{p:07X}" for t in tabelas for p, ptr, _ in t["todas"]
                if ptr - 0x08000000 == off
            ], "jp": txt, "pt": "", "chars": len(txt)}
            for off, txt in sorted(distintas.items())
        ],
    }
    destino = OUT / "ui_originais.json"
    destino.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                       encoding="utf-8")
    print(f"\n  gravado: {destino.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
