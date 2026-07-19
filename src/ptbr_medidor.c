#include "global.h"

/*
 * Medidor de texto para o VWF - substitui sub_0800B130.
 *
 * O ORIGINAL conta CARACTERES. Como cada caractere ocupava 12px fixos, contar
 * caractere era o mesmo que medir largura, e os 12 chamadores usam o resultado
 * exatamente assim: como largura.
 *
 *   asm/code_copy.s:9844            3n/2 + 3   = largura da janela, em tiles
 *   asm/code_small_structures.s     (30 - 3n/2)/2 = X centralizado, em tiles
 *                                   (30 tiles = os 240px da tela)
 *
 * Ao converter o RENDERIZADOR para pixels sem converter o MEDIDOR, as duas
 * metades passaram a falar unidades diferentes: o texto encolheu para ~7,35px
 * por letra, mas a janela continuou sendo dimensionada a 12px por letra. Dai a
 * caixa larga demais com o texto encostado a esquerda.
 *
 * A SAIDA CONTINUA NA MESMA UNIDADE do original - "quantos caracteres de 12px
 * este texto ocupa" - so que agora medida de verdade. Assim os 12 chamadores
 * seguem funcionando sem precisar de patch, e a centralizacao acerta sozinha.
 *
 * ARREDONDAMENTO: para o MAIS PROXIMO, nao para cima.
 * Com arredondamento para cima o titulo "Salvar?" (39px reais) era contado como
 * 4 celulas = 48px, e a centralizacao empurrava o texto 4,5px para a direita -
 * visivel a olho nu, enquanto "Sim" e "Nao" (erro de 1px) pareciam certos. Ao
 * meio da celula o erro cai para no maximo 6px em vez de 11, e com a folga de
 * moldura do passo 4d do patch nao ha risco de a caixa ficar curta.
 */

#define LARGURA_CELULA 12

/* Converte codigo do texto em ponteiro para o glifo. E a mesma rotina que o
 * renderizador usa (data/ptbr_renderer.s a chama duas vezes). */
extern const u16 *sub_0800348C(u16 codigo);

/* Tabela de substituicao: nomes, termos do jogo. Entradas de 9 half-words. */
extern u16 gUnk_03005580[];

extern const u8 gPtBrLarguras[];
extern u16 *gUnk_03002984;

#define CODIGO_MASCARA  0xF0FF
#define CODIGO_MACRO    0xC083  /* expande da tabela de substituicao */
#define CODIGO_IGNORA   0x7087  /* nao ocupa espaco */
#define MACRO_INDICE    0x0F00
#define MACRO_PASSO     9       /* half-words por entrada */

static s32 largura_do_codigo(u16 codigo)
{
    const u16 *glifo;
    const u8 *base;
    s32 desloc;
    s32 avanco;

    glifo = sub_0800348C(codigo);
    base = (const u8 *)gUnk_03002984;
    if (glifo == NULL || base == NULL)
        return LARGURA_CELULA;

    desloc = (s32)((const u8 *)glifo - base);
    if (desloc < 0)
        return LARGURA_CELULA;

    avanco = gPtBrLarguras[desloc >> 3];
    if (avanco <= 0 || avanco > LARGURA_CELULA)
        return LARGURA_CELULA;

    return avanco;
}

/*
 * Devolve a largura do texto em celulas de 12px, arredondada para cima.
 * Mesma caminhada de sub_0800B130 (asm/code_copy.s:3635), somando pixels em vez
 * de contar caracteres.
 */
u32 PtBrMedeTexto(const u16 *texto)
{
    s32 pixels;
    u16 codigo;
    const u16 *macro;

    pixels = 0;
    if (texto == NULL)
        return 0;

    for (;;)
    {
        codigo = *texto;

        if ((codigo & CODIGO_MASCARA) == CODIGO_MACRO)
        {
            /* O indice vem dos bits 8-11; cada entrada tem 9 half-words. */
            macro = &gUnk_03005580[((codigo & MACRO_INDICE) >> 8) * MACRO_PASSO];
            while (*macro != 0)
            {
                pixels += largura_do_codigo(*macro);
                macro++;
            }
            texto++;
            continue;
        }

        if ((codigo & CODIGO_MASCARA) == CODIGO_IGNORA)
        {
            texto++;
            continue;
        }

        if (codigo == 0)
            break;

        pixels += largura_do_codigo(codigo);
        texto++;
    }

    return (u32)((pixels + LARGURA_CELULA / 2) / LARGURA_CELULA);
}
