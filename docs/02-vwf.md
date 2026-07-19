# O motor de fonte de largura variável

Tudo aqui foi **medido**, não deduzido. Deduzir custou cinco versões quebradas —
ver [06-armadilhas.md](06-armadilhas.md).

Os instrumentos usados estão no repositório e podem ser rodados de novo:

| ferramenta | o que mediu |
|---|---|
| `tools/csm3_text/thumb.py` | interpretador ARM Thumb, para executar o desenhador original fora do jogo |
| `tools/csm3_text/mapear_destino.py` | o layout do buffer de destino |
| `tools/csm3_text/medir_sombra.py` | o deslocamento das sombras |
| `tools/csm3_text/comparar_blitters.py` | o desenhador novo contra o original, glifo a glifo |
| `scratchpad/gdbrsp.py` | cliente do protocolo GDB para ler registradores do jogo rodando no mGBA |

---

## O buffer de destino

O texto é **camada de fundo com tilemap**, não sprite. Cada caractere ocupa
2×2 tiles (16×16 px), e os tiles são alocados em pares consecutivos, um par por
coluna de 8 pixels.

```
0x00  colunas 0-7,  linhas 0-7      0x40  colunas 8-15, linhas 0-7
0x20  colunas 0-7,  linhas 8-15     0x60  colunas 8-15, linhas 8-15
```

O endereço de um pixel:

```c
byte = (coluna >> 3) * 0x40
     + (linha  >> 3) * 0x20
     + (linha  &  7) * 4
     + ((coluna & 7) >> 1);

// coluna par usa a metade BAIXA do byte; ímpar, a metade ALTA
```

Confirmado no visualizador de tiles do mGBA: "Sim" (3 letras) ocupa 4 colunas de
tile, e os índices vêm em pares — 448/449 são topo e base da primeira coluna,
450/451 da segunda, e assim por diante.

## O glifo

12 linhas de 2 bytes. O byte 0 traz os pixels 0-7 (bit alto primeiro); a metade
alta do byte 1 traz os pixels 8-11.

## Sombra

Cada pixel aceso gera **tinta** (cor 1) na própria posição e **sombra** (cor 2) à
direita e na diagonal abaixo-à-direita. Onde as duas caem, sai 3. A sombra que
cairia abaixo da linha 11 é descartada.

## Cor de fundo — o erro que a paleta denunciou

O quarto argumento do desenhador chega valendo `0x44444444` — a cor 4 repetida,
que é o bege do interior da caixa. **O que parecia "limpeza de buffer" é pintura
de fundo.** Pintar com zero deixa transparente e a caixa de diálogo fica furada,
deixando ver o cenário atrás.

Mais sutil: a marca não pode ser combinada com o fundo por OR.

```
4 | 1 = 5      ← escreve na paleta 5, não na 1
4 | 2 = 6      ← paleta 6, não 2
```

O certo é **substituir** o fundo e **combinar** apenas com outra marca da própria
letra:

```c
atual = (atual == cor_fundo) ? cor : (atual | cor);
```

Esse defeito passou por um teste automatizado que comparava 47 glifos contra o
desenhador original e dava 47/47 idênticos — porque o teste usava um buffer
**zerado**, onde `0 | 1 = 1` acerta por acidente. No jogo o buffer vem pintado
com 4. Quem achou foi o usuário, comparando pixel a pixel no Aseprite: a letra
misturava `b57352` e `6b0000` em vez de ser sempre `6b0000`.

`comparar_blitters.py` agora testa contra um buffer pré-pintado com a cor 4.

---

## Larguras: por que o recuo importa tanto

A tabela em `data/ptbr_larguras.s` guarda **três medidas por glifo**:

```
[i + 0]  avanço até o próximo glifo, em pixels
[i + 1]  recuo: colunas vazias à esquerda dentro da célula de 12px
[i + 2]  largura da tinta, em colunas
```

Ela é indexada por `(endereço_do_glifo - base_da_fonte) >> 3`. Como cada glifo
ocupa 24 bytes, esse índice vale `glifo * 3` — daí caberem as três medidas sem
gastar memória a mais, e sem precisar dividir por 24 em Thumb (o que exigiria
multiplicação mágica).

O **recuo** é o que torna o espaçamento constante. Calcular o avanço apenas pela
borda direita da tinta deixa o vazio da esquerda intacto, e o espaço entre duas
letras vira:

```
folga_depois(esquerda) + recuo(direita)
```

Como o recuo varia por glifo — `i` tem 6 colunas vazias antes da tinta, `m` tem
1 — o espaço variava de **3px a 8px**. Na tela isso aparecia como "im" colado e
"Si" com buraco. Medido por `tools/csm3_text/medir_bearing.py`.

Descontando o recuo, o desenhador encosta a primeira coluna de tinta na posição
pedida e o espaço fica constante em 0px de variação.

O avanço é `largura_da_tinta + 1 (sombra) + FOLGA`, com `FOLGA` configurável em
`gerar_larguras.py`. Há um gerador de prévia em PNG (`gerar_previa.py`) que
renderiza a mesma frase com folga 0, 1, 2 e 3 para escolher olhando.

---

## Margem superior

O Y da linha é contado em **tiles de 8px**, então não há como afastar o texto 2px
da moldura por ali. Mas o glifo ocupa 12 das 16 linhas do buffer, e sobra espaço:
`MARGEM_TOPO` em `ptbr_blit.c` desce o desenho dentro do buffer.
`2 + 12 + 1 de sombra = 15`, cabe nas 16.

---

## Como o VWF se liga ao jogo

`sub_08001F14` é o renderizador de texto. Ele não pôde ser chamado com `bl` — o
código novo fica a ~32 MB de distância e o `bl` de Thumb só alcança 4 MB. O
linker resolveria inserindo um *veneer*, que muda tamanhos e desloca tudo (foi o
que aconteceu na primeira tentativa: 19.683 faixas alteradas).

A saída é sobrescrever o **início** da função original com um salto indireto,
mantendo o tamanho dela:

```asm
sub_08001F14:
    ldr r3, _PtBrDesvio
    bx  r3
    .align 2, 0
_PtBrDesvio: .4byte PtBrRenderizaTexto+1
    nop
```

Os 10 bytes do prólogo original viram `ldr` + `bx` + literal + `nop`. O corpo
antigo continua ocupando os mesmos bytes, como código morto.

O renderizador novo é **gerado** a partir do original por
`gerar_renderer_vwf.py`, que copia a função e aplica transformações
identificadas por padrão. Gerar em vez de transcrever à mão evita erro de
digitação em 200 linhas de Thumb e deixa o resultado auditável.
