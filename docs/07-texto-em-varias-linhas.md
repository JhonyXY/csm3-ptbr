# Texto em várias linhas

Como uma fala é guardada, e o que foi preciso fazer para o português caber sem
ser cortado.

---

## Uma fala é uma sequência de blocos

O que parece uma fala única é, no bytecode, **uma instrução `0x0308` por linha
de tela**, cada uma no seu offset, com o seu próprio texto:

```
強くなったねぇ…アンタのハンマーから鍛えた魂が伝わってきたよ   (30 caracteres)
  bloco 0x0018C:  8 caracteres  →  強くなったねぇ…
  bloco 0x001A0: 10 caracteres  →  アンタのハンマーから
  bloco 0x001B8: 12 caracteres  →  鍛えた魂が伝わってきたよ
```

`export_falas.py` junta os blocos num texto só, porque traduzir linha isolada
produz português sem sentido — a frase quebra no meio. O campo `estrutura`
guarda os offsets de cada bloco para o caminho de volta.

**O erro que isso causou:** o injetor escrevia a tradução inteira no primeiro
bloco. O texto vazava da caixa e o jogo travava, enquanto as linhas de baixo
ficavam vazias.

---

## A conta do espaço

| | caracteres por linha |
|---|---|
| Japonês, 12px por caractere | 18 |
| Português com VWF, folga 1px | 25 |
| Português com VWF, folga 0px | 29 |
| Português para dizer o que 18 japoneses dizem | ~31 |

O VWF dá mais caracteres por linha que o original, mas não o bastante: o
português precisa de cerca de 1,7x os caracteres do japonês.

Faltando ~20%, havia dois caminhos: **encurtar a tradução** ou **dar mais
espaço**. Este projeto escolheu o segundo.

---

## Inserção de linhas

O injetor **duplica a instrução de texto** quando o português ocupa mais linhas
que o japonês. A quarta linha de uma fala de três passa a existir.

Funciona sem esforço especial porque `rebuild_script` já reconstruía o mapa de
offsets a partir dos **tamanhos novos** de cada instrução:

```
plano = [(opcode, parts, offset_original_ou_None), ...]
```

Instruções inseridas entram com `offset = None`. Só os offsets originais entram
no `offset_map`, que é o que os saltos referenciam — e como as posições novas
são calculadas percorrendo o plano inteiro, tudo que vem depois desloca junto e
os saltos se ajustam sozinhos.

A re-validação confirma: `0 saltos invalidos, 0 opcodes desconhecidos`.

---

## Bloco sobrando é apagado, não ignorado

Quando o português ocupa **menos** linhas que o japonês, sobram blocos. Ignorá-los
deixa o japonês original na tela, no meio da fala traduzida.

O injetor trata lista vazia como "apagar este bloco", gravando string vazia. Foi
o que levou as substituições de 163 para 219 num script de 221 blocos.

---

## Orçamento da tradução

O tradutor recebe `linhas × 25 × 1,6` caracteres. Os 25 são o que cabe numa
linha; o 1,6 é a folga que a inserção cobre.

Sem essa folga o modelo é obrigado a escrever mais seco que o original — foi o
que acontecia com o limite antigo, e o resultado ficava pobre à toa, tendo
espaço disponível.

Existe validação com retentativa dirigida quando o texto passa do orçamento:
medido, instrução no prompt sozinha é desobedecida em **27%** das falas. É o
mesmo padrão que resolveu a flexão de gênero — pedir de novo, dizendo
exatamente o que corrigir, em vez de só rejeitar.

---

## Número de script não é ordem da história

A introdução do jogo é o **script 1603**, não o 11. Injetar "os primeiros 120
scripts" traduz partes espalhadas pelo meio do jogo e deixa a abertura em
japonês.

`achar_fala.py` localiza uma cena a partir de um trecho do japonês que aparece
na tela, e `ver_traduzida.py` responde se ela já foi traduzida e se entrou na
ROM — três perguntas diferentes que é fácil confundir.
