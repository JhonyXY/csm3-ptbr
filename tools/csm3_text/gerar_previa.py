#!/usr/bin/env python3
"""Gera uma previa em PNG do espacamento, para voce escolher olhando.

Renderiza as mesmas frases com a folga variando de 0 a 3 px depois da sombra,
nas cores reais medidas por voce (tinta 6b0000, sombra e7cea5, fundo f7e7c6),
e ainda uma faixa com o original monospace de 12px para comparar.

Roda no Windows, lendo a fonte direto da baserom pelo caminho UNC do WSL.
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROM = REPO / "baserom.gba"
SAIDA = Path("/mnt/c/Users/Jhony/Downloads/decomps/Summon Knight")
sys.path.insert(0, str(Path(__file__).parent))

import csm3rom          # noqa: E402
import font as fontmod  # noqa: E402

TINTA = (0x6B, 0x00, 0x00)
SOMBRA = (0xE7, 0xCE, 0xA5)
FUNDO = (0xF7, 0xE7, 0xC6)
BORDA = (0xB5, 0x73, 0x52)

ESCALA = 4
FRASES = ["Salvar?", "Sim", "Voce quer mesmo", "Ilumina, o Guardiao"]

SJIS = {}
for _i in range(26):
    SJIS[chr(ord("A") + _i)] = 0x8260 + _i
    SJIS[chr(ord("a") + _i)] = 0x8281 + _i
for _i in range(10):
    SJIS[chr(ord("0") + _i)] = 0x824F + _i
SJIS.update({"?": 0x8148, " ": 0x8140, ",": 0x8143, ".": 0x8144, "!": 0x8149})


def escrever_png(caminho, larg, alt, pixels):
    linhas = b""
    for y in range(alt):
        linhas += b"\x00" + bytes(v for x in range(larg) for v in pixels[y][x])
    def bloco(tipo, dados):
        c = tipo + dados
        return struct.pack(">I", len(dados)) + c + struct.pack(">I", zlib.crc32(c))
    png = (b"\x89PNG\r\n\x1a\n"
           + bloco(b"IHDR", struct.pack(">IIBBBBB", larg, alt, 8, 2, 0, 0, 0))
           + bloco(b"IDAT", zlib.compress(linhas, 9))
           + bloco(b"IEND", b""))
    Path(caminho).write_bytes(png)


def main() -> int:
    rom = csm3rom.load_rom(ROM)
    h, _ = fontmod.read_font_header(rom)
    w, hh = h["width"], h["height"]
    dados = rom[h["data_offset"]: h["data_offset"] + h["data_size"]]
    count = h["data_size"] // (fontmod.glyph_bytes_per_row(w) * hh)

    cache = {}

    def glifo(ch):
        if ch in cache:
            return cache[ch]
        code = SJIS.get(ch)
        r = None
        if code is not None:
            idx = fontmod.sjis_to_glyph_index(rom, code)
            if idx is not None and idx < count:
                rows = fontmod.decode_glyph(dados, idx, w, hh)
                a = b = None
                for rr in rows:
                    for c, px in enumerate(rr):
                        if px == "#":
                            a = c if a is None or c < a else a
                            b = c if b is None or c > b else b
                r = (rows, a, b)
        cache[ch] = r
        return r

    # --- monta as telas ---
    LARG = 200
    ALT_LINHA = 18

    def desenhar_frase(tela, y, frase, folga, monospace=False):
        """folga = colunas em branco entre a sombra e a tinta seguinte."""
        x = 2
        for ch in frase:
            g = glifo(ch)
            if g is None:
                x += 6
                continue
            rows, a, b = g
            if a is None:            # espaco
                x += 4 if not monospace else 12
                continue
            desloc = 0 if monospace else a
            for ln in range(12):
                for col in range(12):
                    if rows[ln][col] != "#":
                        continue
                    px = x + col - desloc
                    for dx, dy, cor in ((1, 0, SOMBRA), (1, 1, SOMBRA),
                                        (0, 0, TINTA)):
                        cx, cy = px + dx, y + ln + dy
                        if 0 <= cx < LARG and 0 <= cy < len(tela) and ln + dy < 12:
                            if cor is TINTA or tela[cy][cx] == FUNDO:
                                tela[cy][cx] = cor
            x += 12 if monospace else (b - a + 1) + 1 + folga
        return x

    variantes = [("original monospace 12px", None, True),
                 ("folga 0px (colado na sombra)", 0, False),
                 ("folga 1px", 1, False),
                 ("folga 2px  <- meu palpite", 2, False),
                 ("folga 3px", 3, False)]

    for frase in FRASES:
        alt = ALT_LINHA * len(variantes) + 4
        tela = [[FUNDO] * LARG for _ in range(alt)]
        y = 2
        larguras = []
        for nome, folga, mono in variantes:
            fim = desenhar_frase(tela, y, frase, folga or 0, mono)
            larguras.append((nome, fim - 2))
            for x in range(LARG):
                tela[y + 15][x] = BORDA
            y += ALT_LINHA

        # amplia
        big = [[tela[y // ESCALA][x // ESCALA] for x in range(LARG * ESCALA)]
               for y in range(alt * ESCALA)]
        nome_arq = SAIDA / f"espacamento - {frase.replace('?', '')}.png"
        escrever_png(nome_arq, LARG * ESCALA, alt * ESCALA, big)
        print(f"  gerado: {nome_arq.name}")
        for nome, larg in larguras:
            print(f"      {nome:34s} {larg:4d}px")
        print()

    print("  De cima para baixo, cada faixa e uma variante, na ordem acima.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
