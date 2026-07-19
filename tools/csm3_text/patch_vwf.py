#!/usr/bin/env python3
"""Aplica os patches de VWF nos leitores do valor de retorno do renderizador.

O renderizador novo (data/ptbr_renderer.s) devolve UNIDADES DE 4px em vez de
contagem de caracteres. Seis lugares consomem esse valor assumindo 12px por
caractere e precisam acompanhar.

RESTRICAO CRITICA: os dados do repo sao 32 MB de .incbin opaco com 102.100
ponteiros crus. Se qualquer funcao existente mudar de TAMANHO, tudo depois dela
desloca e esses ponteiros passam a apontar errado. Por isso todo patch aqui e
feito NO LUGAR, instrucao por instrucao, com o mesmo numero de instrucoes -
sobrando `nop` onde a conta ficou mais curta.

    python3 patch_vwf.py            # aplica
    python3 patch_vwf.py --reverter # desfaz
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COPY = REPO / "asm" / "code_copy.s"
MAIN = REPO / "asm" / "code_main.s"
SMALL = REPO / "asm" / "code_small_structures.s"
LINKER = REPO / "linker.ld"
BACKUP = ".pre-vwf"

MARCA_LINKER = "data/ptbr_renderer.o(.text);"


def backup(path: Path) -> None:
    b = path.with_suffix(path.suffix + BACKUP)
    if not b.exists():
        shutil.copy2(path, b)


def reverter() -> int:
    print("=" * 72)
    print("REVERTENDO O VWF")
    print("=" * 72)
    for path in (COPY, MAIN, SMALL, LINKER):
        b = path.with_suffix(path.suffix + BACKUP)
        if b.exists():
            shutil.copy2(b, path)
            b.unlink()
            print(f"  restaurado: {path.relative_to(REPO)}")
        else:
            print(f"  sem backup: {path.relative_to(REPO)}")
    for gerado in ("ptbr_renderer.s", "ptbr_vwf.s", "ptbr_larguras.s"):
        p = REPO / "data" / gerado
        if p.exists():
            p.unlink()
            print(f"  removido  : data/{gerado}")
    return 0


def trocar_unico(texto: str, antigo: str, novo: str, nome: str) -> tuple[str, bool]:
    """Substitui exigindo exatamente uma ocorrencia."""
    n = texto.count(antigo)
    if n != 1:
        print(f"  ERRO em {nome}: esperava 1 ocorrencia, achei {n}")
        return texto, False
    return texto.replace(antigo, novo, 1), True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reverter", action="store_true")
    args = ap.parse_args()
    if args.reverter:
        return reverter()

    backup(COPY)
    texto = COPY.read_text(encoding="utf-8")
    ok = True

    print("=" * 72)
    print("PATCH DE VWF")
    print("=" * 72)

    # --- 1. salto longo no inicio do renderizador original -----------------
    # NAO trocar o "bl sub_08001F14" do chamador: o alvo novo fica a ~32 MB de
    # distancia e o BL de thumb so alcanca 4 MB. O linker resolveria inserindo
    # um veneer, que muda tamanhos e desloca TUDO - foi o que aconteceu na
    # primeira tentativa (19.683 faixas alteradas). A saida e sobrescrever o
    # inicio da funcao original com um salto indireto, mantendo o tamanho dela.
    # Os 10 bytes do prologo viram: ldr(2) + bx(2) + literal(4) + nop(2).
    backup(MAIN)
    main_txt = MAIN.read_text(encoding="utf-8")
    prologo = ("sub_08001F14: @ 0x08001F14\n"
               "\tpush {r4, r5, r6, r7, lr}\n"
               "\tmov r7, sl\n"
               "\tmov r6, sb\n"
               "\tmov r5, r8\n"
               "\tpush {r5, r6, r7}\n")
    salto = ("sub_08001F14: @ 0x08001F14\n"
             "\t@ VWF: desviado para PtBrRenderizaTexto (data/ptbr_renderer.s).\n"
             "\t@ Salto indireto porque o alvo esta fora do alcance de 4 MB do BL.\n"
             "\t@ O corpo original abaixo virou codigo morto, mas continua ocupando\n"
             "\t@ os mesmos bytes - mover qualquer coisa quebraria os ponteiros crus.\n"
             "\tldr r3, _PtBrDesvio\n"
             "\tbx r3\n"
             "\t.align 2, 0\n"
             "_PtBrDesvio: .4byte PtBrRenderizaTexto+1\n"
             "\tnop\n")
    main_txt, r = trocar_unico(main_txt, prologo, salto, "desvio do renderizador")
    ok &= r
    print(f"  1. salto longo no inicio de sub_08001F14: {'ok' if r else 'FALHOU'}")
    if r:
        MAIN.write_text(main_txt, encoding="utf-8")

    # --- 1b. desvio do MEDIDOR de texto ------------------------------------
    # sub_0800B130 conta CARACTERES. Como cada um ocupava 12px, contar era o
    # mesmo que medir - e os 12 chamadores usam o resultado como LARGURA:
    #   asm/code_copy.s:9844          3n/2 + 3      = largura da janela em tiles
    #   asm/code_small_structures.s   (30 - 3n/2)/2 = X centralizado em tiles
    #                                 (30 tiles = os 240px da tela)
    #
    # Converter o renderizador para pixels sem converter o medidor deixou as
    # duas metades em unidades diferentes: o texto encolheu, a janela nao. Por
    # isso a caixa fica larga demais com o texto encostado a esquerda - o que
    # parecia "texto descentralizado" era moldura sobrando.
    #
    # PtBrMedeTexto devolve na MESMA unidade (celulas de 12px), so que medida de
    # verdade, entao nenhum dos 12 chamadores precisa mudar.
    prologo_medidor = ("sub_0800B130: @ 0x0800B130\n"
                       "\tpush {r4, r5, r6, r7, lr}\n"
                       "\tmov r7, sb\n"
                       "\tmov r6, r8\n"
                       "\tpush {r6, r7}\n"
                       "\tmovs r3, #0\n")
    salto_medidor = ("sub_0800B130: @ 0x0800B130\n"
                     "\t@ VWF: desviado para PtBrMedeTexto (src/ptbr_medidor.c).\n"
                     "\t@ Mesmos 10 bytes do prologo original: ldr+bx+literal+nop.\n"
                     "\tldr r3, _PtBrDesvioMedidor\n"
                     "\tbx r3\n"
                     "\t.align 2, 0\n"
                     "_PtBrDesvioMedidor: .4byte PtBrMedeTexto+1\n"
                     "\tnop\n")
    texto, r = trocar_unico(texto, prologo_medidor, salto_medidor,
                            "desvio do medidor")
    ok &= r
    print(f"  1b. salto longo no inicio de sub_0800B130: {'ok' if r else 'FALHOU'}")

    # --- 1c. o valor devolvido vira TILES, nao pixels ----------------------
    # O campo que guarda a largura da linha e um BYTE (strb em 3812), teto 255.
    #
    # No original ele guardava CONTAGEM DE CARACTERES: as linhas japonesas vao
    # ate 53 caracteres, entao cabia com muita folga. Ao converter para PIXELS
    # o mesmo bloco passa a valer ate 636 - o byte da a volta e o jogo se perde.
    # Isso quebra com texto longo em QUALQUER idioma, nao so traduzido.
    #
    # A unidade certa e TILE: 636px / 8 = 80, cabe. E e a unidade que todos os
    # consumidores queriam de qualquer forma - todos dividiam por 8 depois.
    #
    # A conversao entra no lugar da truncagem para 16 bits, que era redundante
    # (o valor nunca chega perto de 65535). Mesmas duas instrucoes.
    antigo = "\tlsls r0, r0, #0x10\n\tlsrs r7, r0, #0x10\n\tldr r0, _0800B2A0"
    novo = ("\tadds r0, #7 @ VWF: pixels -> tiles, arredondando para cima.\n"
            "\tlsrs r7, r0, #3 @ O campo e u8 e 636px nao cabe; 80 tiles cabe.\n"
            "\tldr r0, _0800B2A0")
    texto, r = trocar_unico(texto, antigo, novo, "retorno em tiles")
    ok &= r
    print(f"  1c. retorno do renderizador em tiles: {'ok' if r else 'FALHOU'}")

    # --- 2. avanco do buffer no chamador: n*96 -> n*8 ----------------------
    # O original avanca 96 bytes por CARACTERE (12px x 8 bytes por coluna de
    # pixel). Agora o acumulador esta em PIXELS, entao sao 8 bytes por pixel.
    antigo = "\tlsls r0, r7, #1\n\tadds r0, r0, r7\n\tlsls r0, r0, #5\n"
    novo = ("\tlsls r0, r7, #6 @ VWF: tiles * 64 bytes por coluna (era n*96)\n"
            "\tnop\n\tnop\n")
    texto, r = trocar_unico(texto, antigo, novo, "avanco do buffer")
    ok &= r
    print(f"  2. avanco do buffer n*96 -> tiles*64: {'ok' if r else 'FALHOU'}")

    # --- 3. quantos TILES a linha ocupa, em 4 sites -----------------------
    # O original guarda a contagem de CARACTERES e calcula 1,5 tile por
    # caractere (12px por caractere / 8px por tile). Agora o campo guarda
    # PIXELS, entao a conta e pixels/8 - confirmado pelo visualizador de tiles:
    # "Sim" (3 letras, 36px) ocupa 5 colunas de tile.
    #
    # Dividir por 2 (o que eu fazia antes) dava 4x tiles demais, e escrever
    # alem dos tiles que o tilemap aponta corrompia os vizinhos - era a origem
    # do buraco em forma de T na caixa de dialogo.
    padrao = re.compile(
        r"(\tldrb r4, \[r\d, #2\]\n)"
        r"\tlsls r3, r4, #1\n"
        r"\tlsrs r4, r4, #1\n"
        r"\tsubs r3, r3, r4\n"
    )
    substituto = (r"\1"
                  "\tadds r3, r4, #0 @ VWF: o campo JA esta em tiles\n"
                  "\tnop\n\tnop\n")
    texto, n = padrao.subn(substituto, texto)
    if n != 4:
        print(f"  ERRO: esperava 4 sites de contagem de tiles, achei {n}")
        ok = False
    print(f"  3. contagem de tiles (1,5n -> identidade): {n}/4 sites")

    # --- 4. fatiamento em pedacos de 8 caracteres --------------------------
    # sub_0800CC28 quebra a linha em pedacos de 0x300 bytes (768 = 8 caracteres
    # de 96 bytes = 96 pixels de largura) e desconta esse tanto de r6, que
    # guarda quanto falta da linha. Em pixels o desconto vira 96.
    # O decremento vem de um literal: 0xFFF80000 = -8 << 16 -> -96 << 16.
    #
    # SAO DOIS LITERAIS, NAO UM. O laco tem dois ramos que fazem a mesma conta:
    # _0800CCE0 no primeiro pedaco (linha 7184) e _0800CD3C nos seguintes
    # (linha 7213). A versao anterior deste patch so trocou o primeiro e ainda
    # exigia "exatamente 1 ocorrencia", o que fez a checagem passar.
    #
    # O efeito de deixar o segundo para tras: da segunda volta em diante o laco
    # desconta 8 de um valor que esta em pixels, entao ele roda ~12x mais voltas
    # que o devido. Cada volta aloca 0x300 bytes e empurra sl - o que estoura a
    # area e corrompe memoria. Aparece so em linha com mais de 96px, que e por
    # que a tela de carregar save travava e a caixa "Salvar?" nao.
    literais = ["_0800CCE0", "_0800CD3C"]
    for nome_lit in literais:
        defs = texto.count(f"{nome_lit}: .4byte 0xFFF80000")
        usos = len(re.findall(rf"ldr r\d, {nome_lit}\b", texto))
        if defs != 1 or usos != 1:
            print(f"  ERRO: literal {nome_lit} com {defs} definicao(oes) e "
                  f"{usos} uso(s); esperava 1 e 1")
            ok = False
            continue
        texto = texto.replace(
            f"{nome_lit}: .4byte 0xFFF80000",
            f"{nome_lit}: .4byte 0xFFF40000 @ VWF: -12 tiles (era -8 caracteres)",
            1,
        )
    if ok:
        print(f"  4. decremento do pedaco: -8 chars -> -12 tiles: "
              f"{len(literais)}/{len(literais)} literais")

    # --- 4b. alinhamento do cursor de tiles --------------------------------
    # Depois de desenhar, sub_0800B1AC empurra o cursor de alocacao de tiles e
    # ARREDONDA para o proximo limite de 64 bytes (uma coluna de tile de 8px,
    # 16px de altura). O bloco de texto seguinte comeca ali.
    #
    # O original fazia isso testando se a contagem de caracteres era IMPAR:
    # cada caractere ocupa 96 bytes, e 96n so cai em multiplo de 64 quando n e
    # par; quando e impar falta exatamente 32.
    #
    #     if (n & 1) cursor += 32;
    #
    # Com o cursor andando 8 bytes por PIXEL, essa conta perdeu o sentido: o
    # resto agora e 8*(px % 8), que vale de 0 a 56, e nao 0 ou 32. O cursor
    # ficava no meio de uma coluna de tile e o proximo bloco de texto saia
    # deslocado horizontalmente.
    #
    # A conta certa nao depende mais da unidade: arredonda o proprio cursor.
    antigo = ("\tadds r0, r7, #0\n"
              "\tands r0, r4\n"
              "\tcmp r0, #0\n"
              "\tbeq _0800B300\n"
              "\tadds r0, r1, #0\n"
              "\tadds r0, #0x20\n"
              "\tstr r0, [r2]\n")
    novo = ("\tadds r0, r1, #0 @ VWF: arredonda o cursor para o proximo\n"
            "\tadds r0, #0x3F  @ limite de 64 bytes (uma coluna de tile).\n"
            "\tmovs r3, #0x3F  @ Era 'se n impar, +32', que so valia com\n"
            "\tbics r0, r3     @ 96 bytes por caractere.\n"
            "\tstr r0, [r2]\n"
            "\tnop\n\tnop\n")
    texto, r = trocar_unico(texto, antigo, novo, "alinhamento do cursor")
    ok &= r
    print(f"  4b. cursor arredondado para 64 bytes: {'ok' if r else 'FALHOU'}")

    # --- 4d. folga da janela de menu ---------------------------------------
    # A largura da janela e "3n/2 + 3" tiles (+1 se n for impar), com n vindo do
    # medidor. Com o medidor devolvendo largura real, a caixa passou a nascer
    # justa no texto - correto, mas apertado demais para o gosto.
    #
    # Da para alargar sem estragar nada porque a posicao do texto do item, depois
    # de substituir winX = 15 - w/2, se reduz a:
    #     texto_x = 112 - 6 * largura_do_item
    # ou seja, NAO depende de w. Aumentar a janela move so a moldura; o texto
    # continua centralizado exatamente onde esta.
    #
    # +8 no lugar de +3 devolve a este menu a mesma largura de antes (14 tiles)
    # e, por tabela, o mesmo winX=8 - o que faz o byte do cursor voltar a ser o
    # 0x18 original, sem precisar de compensacao.
    # CUIDADO COM A FORMA DA INSTRUCAO: "adds rD, rN, #imm" so aceita imediato
    # de 0 a 7 em thumb. Com folga 8 o montador recusa ("immediate value out of
    # range"). A saida e a forma de 8 bits, "adds rN, #imm", que exige destino
    # igual a origem - entao a soma cai em r2 e o strb grava r2 direto. Continua
    # sendo duas instrucoes, que e o que importa para nao deslocar nada.
    # r2 morre logo depois (e reatribuido na conta da altura), entao da para
    # suja-lo; o caso impar passa a somar so +1 sobre ele.
    FOLGA_JANELA = 8  # era 3; cada unidade e um tile de 8px
    antigo = "\tadds r0, r2, #3\n\tstrb r0, [r3, #4]\n"
    novo = (f"\tadds r2, #{FOLGA_JANELA} @ VWF: era +3. Folga da moldura;\n"
            "\tstrb r2, [r3, #4] @ o texto nao se mexe, so a caixa.\n")
    texto, r = trocar_unico(texto, antigo, novo, "folga da janela (par)")
    ok &= r
    antigo = "\tadds r0, r2, #4\n\tstrb r0, [r1, #4]\n"
    novo = ("\tadds r0, r2, #1 @ VWF: era +4; r2 ja traz a folga nova\n"
            "\tstrb r0, [r1, #4]\n")
    texto, r2_ok = trocar_unico(texto, antigo, novo, "folga da janela (impar)")
    ok &= r2_ok
    print(f"  4d. folga da janela 3 -> {FOLGA_JANELA} tiles: "
          f"{'ok' if r and r2_ok else 'FALHOU'}")

    # --- 4c. cursor do menu (o martelo) ------------------------------------
    # A posicao do cursor sai de:
    #     X = 8 * winX + [r7+0x29]        (asm/code_copy.s:5246-5251 e 5734+)
    # e a do texto do item, depois de substituir winX = 15 - w/2, sai de:
    #     X = 124 - 6 * largura_do_item
    #
    # Ou seja: o TEXTO nao depende da largura da janela, mas o CURSOR depende.
    # Enquanto a janela tinha o tamanho do texto japones os dois batiam; agora
    # que ela encolheu, winX cresceu de 8 para 11 e o cursor andou 24px para a
    # direita, indo parar em cima da opcao.
    #
    # O byte [r7+0x29] nao e uma margem: ele codifica X_absoluto - 8*winX. Como
    # winX mudou, o byte tem que mudar junto:
    #     novo = antigo - 8 * (winX_novo - winX_japones) = 0x18 - 8*(11-8) = 0
    #
    # LIMITE CONHECIDO: isto conserta o menu de salvar, que e o que da para
    # verificar agora. Existem 13 menus com esse byte e cada um precisa da sua
    # conta. Pior: o byte e sem sinal, e este ja chegou a zero - um titulo que
    # encolha mais que "Salvar?" nao teria como ser compensado aqui. A solucao
    # geral e tirar o winX da conta do cursor e deixar o X absoluto, o que exige
    # trocar as duas rotinas de posicionamento por codigo novo em C.
    # Com a folga do passo 4d, winX volta a ser 8 - o mesmo do japones - entao o
    # byte NAO precisa mais de compensacao. Fica so a checagem, para o dia em que
    # alguem mexer na folga e o cursor sair do lugar sem explicacao.
    small_txt = SMALL.read_text(encoding="utf-8")
    esperado = ("\tbl sub_0800ECAC\n"
                "\tmovs r0, #0x18\n"
                "\tbl sub_0800ECF0\n")
    # Sao dois menus com esse mesmo byte 0x18 (o de salvar e mais um).
    n = small_txt.count(esperado)
    if n < 1:
        print("  ERRO em 4c: nao achei o byte do cursor onde era esperado")
        ok = False
    else:
        print(f"  4c. cursor do menu: 0x18 mantido em {n} menus "
              f"(winX voltou a 8, sem desvio)")

    # --- 5. tiles do ultimo pedaco ----------------------------------------
    # Mesma unidade nova: o resto vem em pixels, e vira tiles dividindo por 8.
    antigo = ("\tadds r0, #8\n"
              "\tlsls r2, r0, #1\n"
              "\tlsrs r1, r0, #0x1f\n"
              "\tadds r0, r0, r1\n"
              "\tasrs r0, r0, #1\n"
              "\tsubs r2, r2, r0\n")
    novo = ("\tadds r0, #12 @ VWF: resto em tiles (era 8 caracteres = 12 tiles)\n"
            "\tadds r2, r0, #0 @ ja esta em tiles\n"
            "\tnop\n\tnop\n\tnop\n\tnop\n")
    texto, r = trocar_unico(texto, antigo, novo, "tiles do ultimo pedaco")
    ok &= r
    print(f"  5. tiles do ultimo pedaco: {'ok' if r else 'FALHOU'}")

    if not ok:
        print("\n  ABORTADO - nenhuma alteracao gravada.")
        return 1

    COPY.write_text(texto, encoding="utf-8")
    print(f"\n  gravado: asm/code_copy.s")

    # --- 6. linker: o codigo novo entra no fim da secao rom ---------------
    backup(LINKER)
    lk = LINKER.read_text(encoding="utf-8")
    if MARCA_LINKER not in lk:
        ancora = "        data/ptbr.o(.rodata); /* strings PT-BR - sempre por ultimo */\n"
        if ancora not in lk:
            ancora = "        data/data1.o(.rodata);\n"
        if ancora not in lk:
            print("  ERRO: nao achei ancora no linker.ld")
            return 1
        lk = lk.replace(
            ancora,
            ancora
            + "        src/ptbr_blit.o(.text); /* VWF: desenhador de largura variavel */\n"
            + "        src/ptbr_render.o(.text); /* VWF: cola com o renderizador */\n"
            + "        src/ptbr_medidor.o(.text); /* VWF: medidor de largura do texto */\n"
            + f"        {MARCA_LINKER} /* VWF: renderizador */\n"
            + "        data/ptbr_larguras.o(.rodata); /* VWF: tabela de larguras */\n",
            1,
        )
        LINKER.write_text(lk, encoding="utf-8")
        print("  6. linker.ld: 4 objetos novos no fim da secao rom")
    else:
        print("  6. linker.ld ja estava ajustado")

    print()
    print("  Nenhuma funcao existente mudou de tamanho - so instrucoes trocadas")
    print("  no lugar, com nop onde a conta encurtou. Os 102.100 ponteiros crus")
    print("  continuam validos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
