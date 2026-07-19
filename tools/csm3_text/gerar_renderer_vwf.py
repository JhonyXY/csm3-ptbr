#!/usr/bin/env python3
"""Gera a versao VWF do renderizador de texto, a partir do original.

Copia `sub_08001F14` de asm/code_main.s, renomeia os simbolos e aplica as
transformacoes de VWF. Gerar em vez de transcrever a mao evita erro de
digitacao em 200 linhas de thumb e deixa o resultado auditavel: da para
rodar de novo e comparar.

O original NAO e tocado - vira codigo morto quando a unica chamada for
redirecionada.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ORIGEM = REPO / "asm" / "code_main.s"
DESTINO = REPO / "data" / "ptbr_renderer.s"

FUNC = "sub_08001F14"
NOVO_NOME = "PtBrRenderizaTexto"
PREFIXO = "_PtBrR"

CABECALHO = '''\t.include "asm/macros.inc"
\t.include "constants/constants.inc"

\t.syntax unified

\t.text

@ =============================================================================
@ Renderizador de texto com VWF quantizado - copia de sub_08001F14.
@ GERADO por tools/csm3_text/gerar_renderer_vwf.py - nao editar a mao.
@
@ Diferencas em relacao ao original:
@   1. r7 acumula UNIDADES DE 4px em vez de contar caracteres
@   2. o avanco do destino vira largura*32 bytes em vez de 0x60 fixo
@   3. a posicao X vira r7>>1 em vez de r7*1,5
@   4. os blitters sao chamados pelos envelopes que devolvem a largura
@
@ O valor de retorno passa a ser em unidades de 4px. Os leitores desse valor
@ estao ajustados por tools/csm3_text/patch_vwf.py.
@ =============================================================================

'''


def extrair_funcao(texto: str, nome: str) -> list[str]:
    linhas = texto.splitlines()
    inicio = None
    for i, l in enumerate(linhas):
        if l.strip() == f"thumb_func_start {nome}":
            inicio = i
            break
    if inicio is None:
        raise SystemExit(f"nao achei thumb_func_start {nome}")

    fim = len(linhas)
    for i in range(inicio + 1, len(linhas)):
        if linhas[i].strip().startswith(("thumb_func_start", "arm_func_start")):
            fim = i
            break
    return linhas[inicio:fim]


def main() -> int:
    texto = ORIGEM.read_text(encoding="utf-8")
    corpo = extrair_funcao(texto, FUNC)
    print(f"  extraidas {len(corpo)} linhas de {FUNC}")

    # --- renomeia os rotulos locais para nao colidir com o original ---
    rotulos = set()
    for l in corpo:
        for m in re.finditer(r"\b_0[0-9A-Fa-f]{7}\b", l):
            rotulos.add(m.group(0))
    print(f"  rotulos locais renomeados: {len(rotulos)}")

    saida = []
    for l in corpo:
        if l.strip() == f"thumb_func_start {FUNC}":
            saida.append(f"\tthumb_func_start {NOVO_NOME}")
            continue
        if l.startswith(f"{FUNC}:"):
            saida.append(f"{NOVO_NOME}: @ VWF quantizado")
            continue
        for r in rotulos:
            l = re.sub(rf"\b{r}\b", PREFIXO + r[1:], l)
        saida.append(l)

    corpo = saida
    trocas = {"blit0": 0, "blit4": 0, "avanco": 0, "posicao": 0}

    # --- 1. os dois blitters viram a MESMA chamada -----------------------
    # O desenhador novo aceita qualquer posicao em pixels, entao a distincao
    # entre fase 0 e fase 4 deixa de existir. Ambos passam a chamar
    # PtBrBlitEAvanca(glifo, base_da_linha, x) -> avanco em pixels.
    for i, l in enumerate(corpo):
        if "bl sub_08003BC0" in l:
            corpo[i] = l.replace("bl sub_08003BC0",
                                 "bl PtBrBlitEAvanca @ (glifo, base, x) -> avanco")
            trocas["blit0"] += 1
        elif "bl sub_08003EB8" in l:
            corpo[i] = l.replace("bl sub_08003EB8",
                                 "bl PtBrBlitEAvanca @ (glifo, base, x) -> avanco")
            trocas["blit4"] += 1

    # O terceiro argumento (r2) era um parametro do original; agora precisa ser
    # a posicao em pixels, que vive em r7.
    for i, l in enumerate(corpo):
        if l.strip() == "mov r2, sl" and i + 1 < len(corpo) \
                and "PtBrBlitEAvanca" in (corpo[i + 1] or ""):
            corpo[i] = "\tadds r2, r7, #0 @ x em pixels (era o parametro sl)"
        elif l.strip() == "mov r2, sl" and i + 2 < len(corpo) \
                and "PtBrBlitEAvanca" in (corpo[i + 2] or ""):
            corpo[i] = "\tadds r2, r7, #0 @ x em pixels (era o parametro sl)"

    # --- 2. avanco fixo vira avanco por largura ---
    # Padrao: "adds r4, #0x60" seguido, em algum ponto proximo, de "adds r7, #1".
    novo_corpo = []
    i = 0
    while i < len(corpo):
        l = corpo[i]
        if l is None:
            i += 1
            continue
        if l.strip() == "adds r4, #0x60":
            # r4 NAO avanca mais: passa a ser a base fixa da linha. Quem anda e
            # r7, que agora conta PIXELS - e o avanco vem do desenhador.
            novo_corpo.append("\tadds r7, r7, r0 @ x += avanco em pixels "
                              "(r4 fica na base da linha)")
            trocas["avanco"] += 1
            # consome o "adds r7, #1" correspondente, que agora esta embutido
            j = i + 1
            while j < len(corpo) and j < i + 5:
                if corpo[j].strip() == "adds r7, #1":
                    corpo[j] = None
                    break
                j += 1
            i += 1
            continue
        if l is not None:
            novo_corpo.append(l)
        i += 1
    corpo = [l for l in novo_corpo if l is not None]

    # --- 3. posicao X: 1,5*chars vira unidades/2 ---
    # Padrao de 3 linhas: lsls r0,r7,#1 / lsrs r1,r7,#1 / subs r0,r0,r1
    novo_corpo = []
    i = 0
    while i < len(corpo):
        if (i + 2 < len(corpo)
                and corpo[i].strip() == "lsls r0, r7, #1"
                and corpo[i + 1].strip() == "lsrs r1, r7, #1"
                and corpo[i + 2].strip() == "subs r0, r0, r1"):
            novo_corpo.append("\tlsrs r0, r7, #1 @ unidades de 4px -> tiles de 8px")
            trocas["posicao"] += 1
            i += 3
            continue
        novo_corpo.append(corpo[i])
        i += 1
    corpo = novo_corpo

    # Nao ha limpeza de linha: o desenhador pinta o fundo de cada glifo com a
    # cor que vem no estilo (r3), exatamente como o original. Limpar a linha
    # inteira com zero foi o que furou a caixa de dialogo.
    print(f"  chamadas ao desenhador  : {trocas['blit0'] + trocas['blit4']}")
    print(f"  avancos convertidos     : {trocas['avanco']}")
    print(f"  calculos de posicao     : {trocas['posicao']}")

    esperado = {"blit0": 2, "blit4": 2, "avanco": 2, "posicao": 2}
    if trocas != esperado:
        print(f"  ERRO: esperava {esperado}, obtive {trocas}")
        print("  O original pode ter mudado - revise antes de seguir.")
        return 1

    DESTINO.write_text(CABECALHO + "\n".join(corpo) + "\n", encoding="utf-8")
    print(f"  gerado: data/ptbr_renderer.s ({len(corpo)} linhas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
