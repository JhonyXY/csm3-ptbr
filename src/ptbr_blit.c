#include "global.h"

/*
 * Desenhador de glifo com largura variavel, para a traducao PT-BR.
 *
 * TUDO AQUI FOI MEDIDO, nao deduzido - deduzir custou cinco versoes quebradas.
 *   tools/csm3_text/mapear_destino.py  layout do buffer
 *   tools/csm3_text/medir_sombra.py    deslocamento das sombras
 *   scratchpad/observar_blitter.py     cor de fundo, lida do jogo rodando
 *   visualizador de tiles do mGBA      a estrutura de tilemap (ver abaixo)
 *
 * LAYOUT: o texto e camada de FUNDO com tilemap, nao sprite. Cada caractere
 * ocupa 2x2 tiles (16x16 px), e os tiles sao alocados em pares consecutivos,
 * um par por coluna de 8 pixels. Confirmado no visualizador: "Sim" (3 letras,
 * 36px) ocupa 5 colunas de tile.
 *     0x00  colunas 0-7,  linhas 0-7      0x40  colunas 8-15, linhas 0-7
 *     0x20  colunas 0-7,  linhas 8-15     0x60  colunas 8-15, linhas 8-15
 *   byte = (coluna/8)*0x40 + (linha/8)*0x20 + (linha%8)*4 + (coluna%8)/2
 *   coluna par usa a metade BAIXA do byte; impar, a metade ALTA.
 *
 * GLIFO: 12 linhas de 2 bytes. Byte 0 = pixels 0-7 (bit alto primeiro);
 * metade alta do byte 1 = pixels 8-11.
 *
 * SOMBRA: cada pixel aceso gera tinta (cor 1) na propria posicao e sombra
 * (cor 2) a direita e na diagonal abaixo-direita. Onde coincidem sai 3. A
 * sombra abaixo da linha 11 e descartada.
 *
 * FUNDO: o quarto argumento chega valendo 0x44444444 - a cor 4 repetida, que e
 * o bege do interior da caixa. O que parecia "limpeza" e PINTURA DE FUNDO.
 * Pintar com zero deixa transparente e a caixa fica furada.
 */

#define GLIFO_LINHAS 12
#define BUFFER_ALTURA 16
#define COR_TINTA 1
#define COR_SOMBRA 2

/*
 * Respiro entre a moldura de cima e o texto. O Y da linha e contado em TILES
 * (8px), entao nao da para afastar 2px por la; aqui da, porque o glifo e
 * desenhado dentro de um buffer de 16 linhas e so ocupa 12.
 * 2 (margem) + 12 (glifo) + 1 (sombra da ultima linha) = 15, cabe nas 16.
 */
#define MARGEM_TOPO 2

static s32 indice_de(s32 coluna, s32 linha)
{
    return (coluna >> 3) * 0x40 + (linha >> 3) * 0x20 + (linha & 7) * 4
         + ((coluna & 7) >> 1);
}

/*
 * Acende um pixel. A cor SUBSTITUI o fundo, mas COMBINA com outra marca da
 * mesma letra (tinta sobre sombra = 3).
 *
 * Fazer OR direto era o erro: o fundo e a cor 4, entao 4|1 dava 5 e 4|2 dava 6
 * - indices de paleta errados. Na tela isso apareceu como letra com pixels de
 * duas cores misturadas e sombra na cor errada. Meu teste nao pegou porque
 * validava contra um buffer zerado, onde 0|1 = 1 acidentalmente acerta.
 */
static void acender(u8 *destino, s32 coluna, s32 linha, u8 cor, u8 cor_fundo)
{
    s32 i;
    u8 atual;

    if (coluna < 0 || linha < 0 || linha >= BUFFER_ALTURA)
        return;

    i = indice_de(coluna, linha);

    if (coluna & 1)
    {
        atual = (u8)(destino[i] >> 4);
        atual = (atual == cor_fundo) ? cor : (u8)(atual | cor);
        destino[i] = (u8)((destino[i] & 0x0F) | (atual << 4));
    }
    else
    {
        atual = (u8)(destino[i] & 0x0F);
        atual = (atual == cor_fundo) ? cor : (u8)(atual | cor);
        destino[i] = (u8)((destino[i] & 0xF0) | atual);
    }
}

/*
 * Pinta as colunas [x, x + largura) com a cor de fundo da caixa.
 * Mexe so nas metades de byte dessas colunas - a coluna vizinha divide o byte
 * e pode pertencer ao glifo anterior.
 */
static void pintar_fundo(u8 *destino, s32 x, s32 largura, u8 cor)
{
    s32 coluna;
    s32 linha;
    s32 i;

    for (coluna = x; coluna < x + largura; coluna++)
    {
        if (coluna < 0)
            continue;

        for (linha = 0; linha < BUFFER_ALTURA; linha++)
        {
            i = indice_de(coluna, linha);
            if (coluna & 1)
                destino[i] = (u8)((destino[i] & 0x0F) | (cor << 4));
            else
                destino[i] = (u8)((destino[i] & 0xF0) | cor);
        }
    }
}

/*
 * Desenha as colunas [recuo, recuo + largura) do glifo, de modo que a PRIMEIRA
 * coluna com tinta caia exatamente na coluna `x` do buffer.
 *
 * `recuo` e o vazio que o desenhista deixou a esquerda dentro da celula de
 * 12px. Descontar esse vazio e o que torna o espacamento constante: sem isso o
 * espaco entre duas letras era a folga da esquerda MAIS o vazio da direita, que
 * varia de glifo para glifo (medido em medir_bearing.py: de 3px a 8px, e por
 * isso "im" colava e "Si" abria um buraco).
 *
 * Pinta 16 colunas de fundo mas desenha so `largura`: e assim que o original
 * garante que nenhum tile fique sem conteudo, e reduzir essa area foi o que
 * deixou buracos na caixa. Como o avanco sempre passa da sombra, a pintura do
 * glifo seguinte nunca come a sombra do anterior.
 */
void PtBrDesenhaGlifo(const u16 *glifo, u8 *destino, s32 x, s32 recuo,
                      s32 largura, u32 estilo)
{
    s32 linha;
    s32 coluna;
    s32 destino_x;
    s32 destino_y;
    u16 fila;
    u32 aceso;
    u8 cor_fundo;

    if (glifo == NULL || destino == NULL)
        return;

    if (recuo < 0 || recuo >= GLIFO_LINHAS)
        recuo = 0;
    if (largura < 0)
        largura = 0;
    if (recuo + largura > GLIFO_LINHAS)
        largura = GLIFO_LINHAS - recuo;

    cor_fundo = (u8)(estilo & 0x0F);
    pintar_fundo(destino, x, BUFFER_ALTURA, cor_fundo);

    for (linha = 0; linha < GLIFO_LINHAS; linha++)
    {
        fila = glifo[linha];

        for (coluna = recuo; coluna < recuo + largura; coluna++)
        {
            if (coluna < 8)
                aceso = (fila >> (7 - coluna)) & 1;
            else
                aceso = (fila >> (8 + (15 - coluna))) & 1;

            if (aceso)
            {
                destino_x = x + coluna - recuo;
                destino_y = linha + MARGEM_TOPO;
                acender(destino, destino_x + 1, destino_y, COR_SOMBRA,
                        cor_fundo);
                if (linha + 1 < GLIFO_LINHAS)
                    acender(destino, destino_x + 1, destino_y + 1, COR_SOMBRA,
                            cor_fundo);
                acender(destino, destino_x, destino_y, COR_TINTA, cor_fundo);
            }
        }
    }
}
