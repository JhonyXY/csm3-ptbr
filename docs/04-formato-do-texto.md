# O formato do texto e do script

Como o jogo guarda diálogo, e como isso foi descoberto.

---

## Onde o texto mora

Cinco arquivos morto-compactados, acessíveis por offset:

```python
ARCHIVE_OFFSETS = {
    0: 0x0BDA40C,  1: 0x18C8D9C,  2: 0x1718FFC,
    3: 0x14D446C,  4: 0x1E2261C,
}
```

Cada um é um arquivo com cabeçalho simples:

```
u16 count       quantas entradas
u16 version
u32 4
```

seguido de `count` entradas de 8 bytes: offset (u32) e tamanho em unidades de 16
bytes (u32). Implementado em `tools/csm3_text/csm3rom.py`.

O conteúdo é comprimido com **LZ77 tipo 0x10 da BIOS do GBA**. O compressor em
`tools/csm3_text/lz77.py` produz saída 0,5% menor que a original — o que importa
porque texto traduzido cresce e cada byte economizado é um byte a menos de
realocação.

Blobs de script têm cabeçalho `"PSI3"` de 16 bytes.

---

## O bytecode

O script é uma sequência de `u16`. O byte alto do opcode escolhe uma das **cinco
tabelas de despacho**; o byte baixo é o índice dentro dela.

Cada opcode consome um número de palavras que depende dele — e para alguns
depende do *conteúdo*, não só do opcode. Sem saber isso, não dá para caminhar
pelo script, e sem caminhar não dá para achar onde o texto começa e termina.

### Expressões RPN

O opcode `0x0002` (e outros) carrega uma expressão avaliada por `sub_08012578`.
O formato é uma lista de tokens `u16` terminada em `0x0000`:

- O terminador `0x0000` **é consumido** e conta como palavra
- Os tokens `0x0001`, `0x0002` e `0x0003` leem **uma palavra extra** cada
- Os demais são operadores de tamanho 1

Isso foi re-derivado direto de `asm/code_080123E4.s:212-538`: o laço em
`_08012590` lê o token e **avança o IP antes** de testar zero.

### Como o formato foi provado

Não por leitura: por **fechamento**. `verificar_roundtrip.py` caminha por todo o
script, serializa de volta, e confere:

- **0 opcodes desconhecidos**
- **0 saltos inválidos** em 45.762 alvos de salto

Um salto que caia no meio de um operando denuncia erro de tamanho em algum
opcode anterior. Zero em 45.762 é evidência forte de que a tabela de tamanhos
está certa. Esse é o critério de aceitação antes de qualquer injeção.

---

## A codificação dos caracteres

Shift-JIS de **largura total**, gravado como `u16` little-endian, terminado em 0.
Não há charmap: os códigos são o próprio Shift-JIS.

O alfabeto latino já existe na fonte do jogo:

```
0x824F..0x8258   dígitos 0-9
0x8260..0x8279   A-Z
0x8281..0x829A   a-z
0x8140           espaço
0x8148           ?
```

### As acentuadas

Não existem na fonte original. Foram alocadas em `0x8440..0x8458` — um bloco
cirílico que o jogo não usa — e os glifos gravados em 25 slots de fonte
consecutivos que o texto japonês não referencia.

Achar esses slots exige cuidado: os glifos **latinos** não aparecem no texto
japonês e portanto entrariam na lista de "livres". Sobrescrevê-los apagaria as
próprias letras que a tradução usa. `patch_acentos.py` mantém um conjunto de
reservados (latino, pontuação, símbolos) por isso.

Os bitmaps são **compostos**: letra base + acento desenhado por cima, com o
acento em versão compacta nas maiúsculas para não estourar a altura da célula.

O mapeamento caractere → código fica em `_out/acentos_mapa.json`, e `encoder.py`
depende dele. **Sem o arquivo, ele silenciosamente remove os acentos** — ver
[06-armadilhas.md](06-armadilhas.md).

---

## Códigos de controle

Aparecem no meio do texto e não devem ser traduzidos nem reordenados:

| padrão | significado |
|---|---|
| `0xC083` mascarado por `0xF0FF` | substituição: expande um nome da tabela `gUnk_03005580`, 9 half-words por entrada |
| `0x7087` mascarado por `0xF0FF` | não ocupa espaço na medição |

No pipeline de tradução esses códigos são **mascarados** antes de ir para o
modelo (viram marcadores `{a}`, `{g}`, ...) e restaurados depois. A validação
rejeita traduções em que o conjunto de marcadores mudou — foi assim que se
garantiu que nenhum nome de personagem se perdeu.

---

## Extração

`export_falas.py` produz 21.059 falas com contexto. `marcar_genero.py` marca cada
uma como masculina, feminina ou compartilhada, seguindo os ramos da variável
`0x182` — o jogo permite escolher menino ou menina, e uma fala compartilhada com
adjetivo flexionado erra para metade dos jogadores.
