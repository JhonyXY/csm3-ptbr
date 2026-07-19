#!/usr/bin/env python3
"""Verifica a ROM com VWF: confirma que nada existente deslocou.

Se qualquer funcao tivesse mudado de tamanho, tudo depois dela andaria e os
diffs apareceriam como faixas enormes e contiguas. O esperado sao poucas faixas
pequenas (as instrucoes trocadas) mais a area nova no fim.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom

REPO = Path(__file__).resolve().parents[2]
FIM_DADOS_ORIGINAIS = 0x1FBB1ED


def main() -> int:
    base = csm3rom.load_rom(REPO / "baserom.gba")
    nova = csm3rom.load_rom(REPO / "csm3.gba")

    faixas = []
    inicio = None
    for i in range(len(base)):
        if base[i] != nova[i]:
            if inicio is None:
                inicio = i
        elif inicio is not None:
            faixas.append((inicio, i))
            inicio = None
    if inicio is not None:
        faixas.append((inicio, len(base)))

    fundidas = []
    for f in faixas:
        if fundidas and f[0] - fundidas[-1][1] <= 32:
            fundidas[-1] = (fundidas[-1][0], f[1])
        else:
            fundidas.append(f)

    print("=" * 72)
    print("DIFERENCAS CONTRA A ROM ORIGINAL")
    print("=" * 72)

    antigas = [f for f in fundidas if f[0] < FIM_DADOS_ORIGINAIS]
    novas = [f for f in fundidas if f[0] >= FIM_DADOS_ORIGINAIS]

    total_antigo = 0
    # A fonte E modificada de proposito (acentuadas + glifos deslocados), entao
    # mudanca ali nao e sinal de deslocamento. So alerta fora dela.
    import font as fontmod
    h, _ = fontmod.read_font_header(base)
    fonte_ini = h["data_offset"]
    fonte_fim = fonte_ini + h["data_size"]

    print(f"\n  --- dentro da area original ({len(antigas)} faixas) ---")
    for s, f in antigas:
        n = f - s
        total_antigo += n
        na_fonte = fonte_ini <= s < fonte_fim
        if na_fonte:
            marca = "  (fonte: glifos reescritos de proposito)"
        elif n > 512:
            marca = "  <== GRANDE, suspeito de deslocamento"
        else:
            marca = ""
        print(f"      0x{s:07X}..0x{f:07X}  {n:6,d} bytes{marca}")

    total_novo = sum(f - s for s, f in novas)
    print(f"\n  --- area apendada ({len(novas)} faixas) ---")
    for s, f in novas:
        print(f"      0x{s:07X}..0x{f:07X}  {f-s:6,d} bytes")

    print()
    print(f"  alterado na area original: {total_antigo:,} bytes")
    print(f"  adicionado no fim        : {total_novo:,} bytes")

    print()
    print("=" * 72)
    print("VEREDITO")
    print("=" * 72)
    grandes = [f for f in antigas
               if (f[1] - f[0]) > 512 and not (fonte_ini <= f[0] < fonte_fim)]
    if grandes:
        print(f"  ALERTA: {len(grandes)} faixa(s) grande(s) na area original.")
        print("  Isso indica que algo mudou de tamanho e deslocou o resto -")
        print("  os ponteiros crus dentro dos .incbin estariam quebrados.")
        return 1

    print(f"  Nenhuma faixa grande na area original: nada deslocou.")
    print(f"  As {len(antigas)} faixas pequenas sao as instrucoes trocadas no lugar")
    print(f"  mais as tabelas de ponteiros reapontadas.")

    # Confere que os simbolos novos existem no mapa do linker.
    mapa = REPO / "csm3.map"
    if mapa.exists():
        texto = mapa.read_text(encoding="utf-8", errors="replace")
        print()
        print("  simbolos novos no mapa do linker:")
        for simbolo in ("PtBrRenderizaTexto", "PtBrBlitFase0", "PtBrBlitFase4",
                        "PtBrLarguraDoGlifo", "gPtBrLarguras"):
            achado = None
            for linha in texto.splitlines():
                if linha.strip().endswith(simbolo):
                    partes = linha.split()
                    if len(partes) >= 2 and partes[0].startswith("0x"):
                        achado = partes[0]
                        break
            estado = achado if achado else "NAO ENCONTRADO"
            print(f"      {simbolo:22s} {estado}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
