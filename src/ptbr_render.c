#include "global.h"

/*
 * Cola entre o renderizador de texto e o desenhador de largura variavel.
 *
 * O renderizador original avanca um PONTEIRO de 0x60 bytes por caractere. Aqui
 * ele acumula uma POSICAO EM PIXELS, e o desenhador escreve nessa posicao.
 *
 * O quarto argumento (estilo) tem que ser repassado: e a cor de fundo da caixa,
 * medida valendo 0x44444444 no jogo rodando.
 */

extern void PtBrDesenhaGlifo(const u16 *glifo, u8 *destino, s32 x, s32 recuo,
                             s32 largura, u32 estilo);

/*
 * Gerada por tools/csm3_text/gerar_larguras.py. Indexada por
 * (endereco_do_glifo - base_da_fonte) / 8, que da 3 entradas por glifo porque
 * cada glifo ocupa 24 bytes. As tres entradas sao usadas:
 *
 *     [i + 0] avanco ate o proximo glifo, em pixels
 *     [i + 1] recuo: colunas vazias a esquerda dentro da celula
 *     [i + 2] largura da tinta, em colunas
 *
 * Antes so a primeira era usada e as outras duas ficavam zeradas - ignorar o
 * recuo era a causa do espacamento irregular.
 */
extern const u8 gPtBrLarguras[];
extern u16 *gUnk_03002984;

#define LARGURA_PADRAO 12

/*
 * Le as tres medidas do glifo. Devolve 0 e cai no comportamento original (12px,
 * sem recuo) se a tabela nao souber responder - assim um glifo desconhecido
 * fica largo demais, nunca sobreposto.
 */
static s32 medidas_do_glifo(const u16 *glifo, s32 *recuo, s32 *largura)
{
    s32 desloc;
    s32 avanco;
    const u8 *base;

    *recuo = 0;
    *largura = LARGURA_PADRAO;

    base = (const u8 *)gUnk_03002984;
    if (base == NULL || glifo == NULL)
        return LARGURA_PADRAO;

    desloc = (s32)((const u8 *)glifo - base);
    if (desloc < 0)
        return LARGURA_PADRAO;

    avanco = gPtBrLarguras[desloc >> 3];
    if (avanco <= 0 || avanco > LARGURA_PADRAO)
        return LARGURA_PADRAO;

    *recuo = gPtBrLarguras[(desloc >> 3) + 1];
    *largura = gPtBrLarguras[(desloc >> 3) + 2];
    if (*recuo < 0 || *recuo >= LARGURA_PADRAO)
        *recuo = 0;
    if (*largura < 0 || *recuo + *largura > LARGURA_PADRAO)
        *largura = LARGURA_PADRAO - *recuo;

    return avanco;
}

/*
 * Desenha um glifo na posicao `x` e devolve quanto avancar, em pixels.
 * O renderizador soma esse retorno ao proprio acumulador, e os sites que
 * contam tiles dividem esse acumulador por 8.
 */
s32 PtBrBlitEAvanca(const u16 *glifo, u8 *destino, s32 x, u32 estilo)
{
    s32 avanco;
    s32 recuo;
    s32 largura;

    if (glifo == NULL || destino == NULL)
        return LARGURA_PADRAO;

    avanco = medidas_do_glifo(glifo, &recuo, &largura);
    PtBrDesenhaGlifo(glifo, destino, x, recuo, largura, estilo);

    return avanco;
}
