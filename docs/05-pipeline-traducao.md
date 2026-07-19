# O pipeline de tradução

Da ROM japonesa ao texto em português dentro do jogo.

---

## Visão geral

```
export_falas.py     →  21.059 falas com contexto
marcar_genero.py    →  marca cada fala M / F / compartilhada
tradutor.py         →  traduz com modelo local, valida, reinjeta
migrar_para_build.py→  grava as strings e reaponta os ponteiros
```

---

## Deduplicação

O jogo repete a mesma fala várias vezes — a animação de rolagem redesenha a
linha em posições diferentes. Das 21.059 falas, **15.332 são distintas**: 27% era
repetição.

Traduzir cada cópia gastaria GPU à toa **e** arriscaria sair diferente em cada
uma. Traduz-se uma vez e aplica-se em todas.

Cuidado: a deduplicação é por texto exato. O jogo tem pares quase idênticos que
ela não pega:

```
これからどこへ行くつもりだったんだろうか…
これからどこへ行くつもりだったんだろう…     ← só muda o か
```

Dar a mesma tradução aos dois é o comportamento certo, não preguiça do modelo.

---

## Gênero

O protagonista pode ser menino **ou** menina — o jogador escolhe. Uma fala
compartilhada com adjetivo flexionado erra para metade dos jogadores, e é o
defeito mais fácil de passar despercebido numa revisão.

`marcar_genero.py` classifica cada fala seguindo os ramos da variável `0x182`.
Falas de ramo exclusivo podem flexionar à vontade; falas compartilhadas, não.

A validação usa uma expressão que só dispara quando o adjetivo vem depois de
cópula referindo-se a quem fala:

```
"fiquei surpreso"   → erro, flexiona
"que surpresa"      → ok, é substantivo
```

Quando dispara, o pipeline **pede a reescrita ao modelo** dizendo exatamente qual
palavra trocar de construção, em vez de simplesmente rejeitar. Resultado medido:
de 5% de falas com flexão indevida para **0 em 658**.

---

## Códigos de controle

Antes de ir ao modelo, os códigos de controle viram marcadores curtos (`{g}`,
`{a}`, ...). Depois voltam. A validação rejeita traduções em que o conjunto de
marcadores mudou — é o que garante que nenhum nome de personagem se perca.

---

## Glossário

Extraído do patch v1.0 existente, comparando bytes: 45 termos com grafia fixada
(nomes de personagem, itens, lugares). Vai no prompt e é conferido depois.

---

## O modelo

Servidor local via `llama-server`, endpoint compatível com OpenAI. `tradutor.py`
descobre o IP do host do Windows lendo `/proc/net/route`, para funcionar de
dentro do WSL.

**Configuração que importa:** `--parallel 1 --ctx-size 16384`. Com
`--parallel 4` o contexto é dividido entre os slots, cada um fica com 2048
tokens, e o modelo devolve **resposta vazia** — sem erro, sem aviso.

---

## O lote que aceitava resposta incompleta

O tradutor manda 12 falas por requisição. A lógica original aceitava o lote se
metade ou mais voltasse:

```python
if len(traduzidas) >= len(lote) / 2:
    break
```

Um lote de 12 que voltava com 9 passava nesse teste, e **as 3 faltantes eram
gravadas como vazias, em silêncio**. Taxa medida: 25% de falas vazias.

O diagnóstico descartou as hipóteses fáceis antes de chegar na certa:

- **Não era corte de resposta** — as falhas se espalhavam pelo lote, não se
  concentravam no fim (verificado por posição)
- **Não era tamanho** — falhas e sucessos tinham o mesmo comprimento médio de
  japonês
- **Não era sobrecarga** — um lote de teste ao vivo voltou 12/12

Agora, quem não volta no lote ganha **uma chamada individual**. Traduzir uma fala
sozinha é o caso mais fácil para o modelo. Efeito: 0 falhas, e o ritmo *dobrou*
(0,2 → 0,4-0,6 falas/s), porque não há mais reprocessamento de vazios.

---

## Retomada

O progresso é gravado a cada lote. Ao reiniciar, o que já passou é pulado. Isso
importa: são horas de GPU e o processo precisa sobreviver a interrupções.

---

## Auditoria

`auditar_traducao.py` procura os defeitos que importam num RPG, sem precisar de
revisão humana linha a linha:

| verificação | por quê |
|---|---|
| flexão de gênero em fala compartilhada | erra para metade dos jogadores |
| redundância ("iam ir", "vou ir") | literalismo do japonês |
| glossário ignorado | nome fora da grafia fixada |
| excesso de reticências | o japonês usa `…` demais; em português cansa |
| japonês que sobrou | o modelo não traduziu |
| marcadores de controle divergentes | nome de personagem perdido |
| passa do limite da caixa | texto cortado na tela |

---

## Capacidade da caixa

`--capacidade` define o teto de caracteres por caixa: **54 sem VWF, 78 com**. É o
VWF que torna a tradução viável — texto em português é cerca de 1,7x o japonês
em caracteres, e sem a economia de 30% por letra boa parte não caberia.
