#!/usr/bin/env python3
"""Validacao final da ROM traduzida.

Confere que:
  - o cabecalho GBA continua intacto (logo da Nintendo, checksum, entry point)
  - NADA fora do archive 2 foi tocado
  - o texto traduzido esta la e le de volta como portugues
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import walker
from script_text import word_to_sjis

REPO = Path(__file__).resolve().parents[2]
ORIG = REPO / "baserom.gba"
NOVA = REPO / "csm3_ptbr.gba"


def header_checksum(rom: bytes) -> int:
    """Checksum do cabecalho GBA (bytes 0xA0..0xBC), conforme a BIOS valida."""
    chk = 0
    for i in range(0xA0, 0xBD):
        chk = (chk - rom[i]) & 0xFF
    return (chk - 0x19) & 0xFF


def main() -> int:
    orig = csm3rom.load_rom(ORIG)
    nova = csm3rom.load_rom(NOVA)

    print("=" * 72)
    print("CABECALHO GBA")
    print("=" * 72)
    logo_ok = orig[0x04:0xA0] == nova[0x04:0xA0]
    titulo = nova[0xA0:0xAC].decode("ascii", "replace")
    game_code = nova[0xAC:0xB0].decode("ascii", "replace")
    chk_stored = nova[0xBD]
    chk_calc = header_checksum(nova)
    print(f"  logo da Nintendo intacto : {logo_ok}")
    print(f"  titulo                   : {titulo!r}")
    print(f"  game code                : {game_code!r}")
    print(f"  entry point              : {nova[0:4].hex()}")
    print(f"  checksum do cabecalho    : gravado 0x{chk_stored:02X}, "
          f"calculado 0x{chk_calc:02X}  {'OK' if chk_stored == chk_calc else 'DIVERGE'}")

    print()
    print("=" * 72)
    print("ESCOPO DA MODIFICACAO")
    print("=" * 72)
    base = csm3rom.ARCHIVE_OFFSETS[csm3rom.SCRIPT_ARCHIVE]
    limite = csm3rom.ARCHIVE_OFFSETS[1]

    antes_ok = orig[:base] == nova[:base]
    depois_ok = orig[limite:] == nova[limite:]
    print(f"  bytes 0x0000000..0x{base:07X} (antes do archive 2) : "
          f"{'identicos' if antes_ok else 'DIFEREM'}")
    print(f"  bytes 0x{limite:07X}..fim   (apos o archive 2) : "
          f"{'identicos' if depois_ok else 'DIFEREM'}")

    diff = sum(1 for a, b in zip(orig[base:limite], nova[base:limite]) if a != b)
    span = limite - base
    print(f"  dentro do archive 2: {diff:,} de {span:,} bytes alterados "
          f"({100*diff/span:.1f}%)")

    print()
    print("=" * 72)
    print("TEXTO TRADUZIDO NA ROM GERADA")
    print("=" * 72)
    auto_map = walker.load_auto_map()
    archive = csm3rom.open_archive(nova, csm3rom.SCRIPT_ARCHIVE)
    script = csm3rom.load_script(archive, 8)
    result = walker.walk(bytes(script.body), auto_map)

    latinos = 0
    for ins in result.text_instructions:
        words = ins.text_words or []
        raw = bytearray()
        for wd in words:
            raw += word_to_sjis(wd)
        try:
            texto = bytes(raw).decode("shift_jis")
        except UnicodeDecodeError:
            continue
        # Faixa latina de largura total: 0xFF21-0xFF3A / 0xFF41-0xFF5A
        if any("Ａ" <= c <= "ｚ" for c in texto):
            latinos += 1
            if latinos <= 12:
                # Converte de largura total para ASCII so para exibir.
                ascii_txt = "".join(
                    chr(ord(c) - 0xFEE0) if "！" <= c <= "～" else
                    (" " if c == "　" else c)
                    for c in texto
                )
                print(f"  @0x{ins.offset:04X}  {ascii_txt}")

    print(f"\n  strings com texto latino: {latinos}")

    todas_ok = logo_ok and chk_stored == chk_calc and antes_ok and depois_ok and latinos > 0
    print()
    print("=" * 72)
    if todas_ok:
        print("RESULTADO: ROM valida, modificacao contida no archive 2, texto presente.")
        return 0
    print("RESULTADO: algo saiu do esperado.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
