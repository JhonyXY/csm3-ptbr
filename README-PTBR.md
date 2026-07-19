# Summon Night: Craft Sword Monogatari 3 — tradução PT-BR

Tradução para português do Brasil de *Summon Night: Swordcraft Story 3 —
Hajimari no Ishi* (GBA), construída sobre o
[disassembly do jiangzhengwenjz](https://github.com/jiangzhengwenjz/csm3).

Este fork **não é um matching decomp**. O upstream busca reproduzir o binário
original a partir de C; aqui o objetivo é outro: traduzir e expandir o jogo,
usando o disassembly como base para modificações que o build system aplica
sozinho.

```
make                → ROM japonesa original, byte a byte
./build-ptbr.sh     → ROM em português
./build-ptbr.sh --reverter   → volta ao decomp original
```

---

## A regra que orienta tudo

> **Nenhum arquivo de assembly do upstream é editado à mão.**
> Toda modificação é aplicada por script, no lugar, instrução por instrução.

Isso não é preciosismo. Os dados do jogo são 32 MB de `.incbin` opaco com
**102.100 ponteiros crus**. Se qualquer função existente mudar de *tamanho*,
tudo depois dela desloca e esses ponteiros passam a apontar para o lugar errado
— sem erro de compilação, sem aviso, só um jogo quebrado de formas difíceis de
rastrear.

Por isso todo patch em código existente troca instruções mantendo a contagem,
completando com `nop` onde a conta encurtou. Código realmente novo entra em
objetos novos, ligados no fim da seção `rom` pelo linker.

`tools/csm3_text/verificar_vwf.py` confere isso a cada build: compara a ROM
construída com a original e falha se alguma faixa grande tiver deslocado.

---

## O que este fork adiciona

### Motor de fonte de largura variável (VWF)

O jogo original desenha todo caractere numa célula fixa de 12 pixels — certo
para japonês, desperdício para o alfabeto latino. O VWF mede cada glifo e avança
só o necessário: **8,34px em média, 30% de economia**, o que é o que permite o
texto em português caber nas caixas.

- `src/ptbr_blit.c` — desenha o glifo com largura e recuo variáveis
- `src/ptbr_render.c` — cola entre o renderizador do jogo e o desenhador
- `src/ptbr_medidor.c` — mede o texto (alimenta o dimensionamento das janelas)

### Acentuação

O jogo não tem `á é í ó ú ã õ â ê ô ç à ü`. Os 25 glifos são **compostos** —
letra base + acento desenhado por cima — e gravados em slots de fonte que o
japonês não usa, com o mapeamento Shift-JIS ajustado para alcançá-los.

### Pipeline de tradução

Extração do texto, deduplicação, tradução por modelo local, validação e
reinjeção com repointing automático. Ver [docs/05-pipeline-traducao.md](docs/05-pipeline-traducao.md).

---

## Documentação

Tudo que foi descoberto por engenharia reversa está em [`docs/`](docs/):

| documento | assunto |
|---|---|
| [01-arquitetura.md](docs/01-arquitetura.md) | como as peças se encaixam e por que |
| [02-vwf.md](docs/02-vwf.md) | o motor de fonte: buffer, sombra, cores, larguras |
| [03-geometria-menus.md](docs/03-geometria-menus.md) | janelas, centralização, cursor |
| [04-formato-do-texto.md](docs/04-formato-do-texto.md) | o bytecode de script e como o texto é guardado |
| [05-pipeline-traducao.md](docs/05-pipeline-traducao.md) | extração, tradução, validação, injeção |
| [06-armadilhas.md](docs/06-armadilhas.md) | os erros que custaram caro, e como evitá-los |

Vale ler [06-armadilhas.md](docs/06-armadilhas.md) antes de mexer em qualquer
coisa. É o documento mais útil do conjunto.

---

## Como construir

Você precisa de:

- A ROM original como `baserom.gba` na raiz
  (`sha1: 3f5253fcf57e07ce52472bd29a61d16b98a12376`)
- O toolchain do decomp — ver [INSTALL.md](INSTALL.md) do upstream
- `devkitARM` (ou equivalente) em `$DEVKITARM`
- Python 3.10+

```sh
export DEVKITARM=$HOME/devkitARM
./build-ptbr.sh
```

O script executa sete passos numa ordem que **não é arbitrária** — as
dependências entre eles estão comentadas no próprio arquivo. Trocar dois de
lugar produz erro silencioso: a build sai, roda, e está errada. Foi o que
aconteceu duas vezes durante o desenvolvimento.

---

## Estado

| | |
|---|---|
| Motor de VWF | funcionando |
| Acentuação | 25 glifos, funcionando |
| Menus de sistema | 43 strings traduzidas |
| Diálogo | 21.059 falas extraídas, tradução em andamento |
| Interface | 525 strings extraídas, não traduzidas |

---

## Créditos e licença

O disassembly base é de [jiangzhengwenjz](https://github.com/jiangzhengwenjz/csm3)
e colaboradores. Este fork preserva o histórico deles.

O upstream não declara licença. *Summon Night: Craft Sword Monogatari 3* é obra
da Flight-Plan e Banpresto — este projeto não distribui a ROM nem qualquer
binário do jogo, apenas ferramentas e o material necessário para aplicar a
tradução sobre uma cópia que você já possua.
