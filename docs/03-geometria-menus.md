# Geometria das janelas e menus

Como o jogo decide onde a caixa fica, onde o texto fica dentro dela, e onde o
cursor aparece. Descoberto ao investigar por que o texto traduzido parecia
descentralizado.

Todas as referências são a `asm/code_copy.s` salvo indicação contrária.

---

## Não existe "alinhamento"

O jogo **não tem** modo centralizado / à esquerda / à direita para ativar. Cada
desenho de texto recebe um **X explícito**, e existem mais de 20 chamadores de
`sub_0800B1AC`, cada um com suas coordenadas.

O que existe é uma fórmula de centralização aplicada por alguns chamadores, a
partir da largura medida do texto — ver abaixo.

---

## Dimensionamento da janela

A largura sai do texto mais largo entre o título e os itens:

```asm
; linhas 4759-4773
ldrb r1, [r5]        ; Wmax, em células de 12px
lsls r0, r1, #1      ; 2n
adds r0, r0, r1      ; 3n
asrs r2, r0, #0xc    ; 3n/2  → largura em tiles
adds r2, #8          ; folga da moldura  (o original somava 3)
strb r2, [r3, #4]
; se n for ímpar, soma 1 a mais
```

`3n/2` porque cada célula tem 12px e cada tile tem 8px. A correção para `n`
ímpar existe porque `12n` só cai em múltiplo de 8 quando `n` é par.

Há um piso: janela nunca fica abaixo de 7 tiles (linhas 4774-4781).

**A folga foi alterada de 3 para 8** neste fork. Com o medidor VWF devolvendo a
largura real, a caixa nascia justa demais no texto. Aumentar a folga é seguro
porque a posição do texto não depende da largura da janela — ver a álgebra
abaixo.

## Posicionamento da janela

Centralizada na tela:

```asm
; linhas 4801-4820
winX = 15 - largura/2      ; 15 tiles = metade dos 30 da tela
winY = 10 - altura/2
```

## Posicionamento do texto

O item é desenhado em `X = 8 × (winX + 2 + r4)`, com `r4` sendo o deslocamento
de centralização do item dentro da janela (linhas 4964-4986).

Substituindo `winX = 15 - w/2`:

```
texto_x = 8 × (15 − w/2 + 2 + (2(w−3) − 3·iw)/4)
        = 112 − 6 × iw
```

**O `w` desaparece.** A posição do texto depende apenas da largura do próprio
item, não do tamanho da janela. Essa invariância é o que permite mexer na folga
da moldura sem mover o texto.

## O cursor

Dois sítios calculam a posição do sprite de cursor (o martelo), com aritmética
idêntica: linhas 5231-5262 e 5734-5759, ambos chamando `sub_0800A678`, que é só
um setter de `obj->x` / `obj->y`.

```
cursor_x = 8 × winX + [r7+0x29]
cursor_y = 8 × (winY + 1 + (tem_título ? 2 : 0)) + (selecionado × 16)
```

`[r7+0x29]` é um byte em pixels, gravado por menu antes de a janela abrir
(`sub_0800ECF0`). Ele **não** é uma margem: guarda `X_absoluto − 8 × winX`.

Comparando as duas fórmulas:

```
texto_x  = 112 − 6·iw          ← não depende de w
cursor_x = 120 − 4·w + offset  ← depende de w
```

Essa assimetria é a raiz do cursor sobrepondo o texto quando a janela muda de
tamanho. No menu de salvar, `winX` foi de 8 para 11 quando a caixa encolheu, e o
cursor andou 24px para a direita sozinho.

**Como isto foi resolvido aqui:** restaurando a largura original da janela (a
folga de 8 acima), `winX` volta a 8 e o byte do cursor volta a valer o `0x18`
original, sem compensação. Solução geral alternativa, não implementada: tirar o
`winX` da conta do cursor e deixá-lo em coordenada absoluta, o que exigiria
substituir as duas rotinas de posicionamento por código novo.

---

## Alocação de tiles entre blocos de texto

Depois de desenhar, o cursor de alocação de tiles é arredondado para o próximo
limite de 64 bytes — uma coluna de tile de 8px por 16px de altura. É onde o
bloco de texto seguinte começa.

O original fazia isso testando se a contagem de caracteres era ímpar: cada
caractere ocupa 96 bytes, e `96n` só cai em múltiplo de 64 quando `n` é par;
quando é ímpar falta exatamente 32.

```c
if (n & 1) cursor += 32;
```

Com o cursor andando 8 bytes por **pixel**, o resto passou a ser `8 × (px % 8)`,
que vale de 0 a 56 — nunca só 0 ou 32. O patch troca por arredondar o próprio
cursor, o que não depende de unidade:

```asm
adds r0, r1, #0
adds r0, #0x3F
movs r3, #0x3F
bics r0, r3
str  r0, [r2]
```

---

## Estruturas

`gUnk_03005180`, stride 28 (0x1C), uma entrada por linha de texto em voo:

| offset | conteúdo |
|---|---|
| +0 | estado da máquina |
| +2 | largura da linha (era contagem de caracteres, agora pixels) |
| +5 | X, em **colunas de tile**, com sinal (`ldrsb`) |
| +6 | Y, em colunas de tile, com sinal |
| +7 | índice da superfície/camada de fundo |
| +0xc / +0xd | atraso do efeito de máquina de escrever |
| +0xe | caracteres por passo |

O campo +5 estar em tiles é importante: **não dá para expressar deslocamento
sub-tile por ali**. Centralização com precisão de pixel só é possível dentro do
renderizador, preenchendo colunas em branco antes do primeiro glifo.
