# Arquitetura

Como as peças se encaixam, e por que estão dispostas assim.

---

## A restrição que define tudo

Os dados do jogo são **32 MB de `.incbin` opaco com 102.100 ponteiros crus**.
Esses ponteiros são endereços absolutos gravados nos dados, apontando uns para os
outros. O disassembly não os conhece — para ele são bytes.

Consequência: se qualquer função existente mudar de **tamanho**, tudo depois dela
desloca e os ponteiros passam a apontar para o lugar errado. Sem erro de
compilação. Sem aviso. O jogo simplesmente se comporta mal de formas difíceis de
rastrear.

Daí as duas regras:

1. **Patch em código existente troca instruções mantendo a contagem**, com `nop`
   onde a conta encurtou.
2. **Código realmente novo entra em objetos novos**, ligados no fim da seção
   `rom` pelo `linker.ld`, onde crescer não desloca nada.

E daí a terceira, que é operacional: **nenhum assembly do upstream é editado à
mão.** Tudo passa por script, para ser reproduzível, auditável e reversível.

`tools/csm3_text/verificar_vwf.py` confere isso: compara a ROM construída com a
original e falha se alguma faixa grande tiver deslocado. Roda no fim de todo
build.

---

## As camadas

```
                        ┌─────────────────────────┐
   baserom.gba  ───────▶│  extração               │──▶ _out/*.json
                        │  walker, opcode_spec    │
                        └─────────────────────────┘
                                    │
                        ┌─────────────────────────┐
                        │  tradução               │──▶ traducao.json
                        │  tradutor.py + modelo   │
                        └─────────────────────────┘
                                    │
                        ┌─────────────────────────┐
                        │  injeção                │──▶ data/ptbr.s
                        │  migrar_para_build      │    data1.s repointado
                        └─────────────────────────┘
                                    │
                        ┌─────────────────────────┐
                        │  fonte                  │──▶ glifos acentuados
                        │  patch_acentos          │    data/ptbr_larguras.s
                        │  gerar_larguras         │
                        └─────────────────────────┘
                                    │
                        ┌─────────────────────────┐
                        │  motor                  │──▶ src/ptbr_*.c
                        │  patch_vwf              │    asm patcheado no lugar
                        │  gerar_renderer_vwf     │
                        └─────────────────────────┘
                                    │
                                 make  ──▶  csm3.gba
```

`build-ptbr.sh` executa isso na ordem certa. A ordem **não é arbitrária** — as
dependências estão comentadas no próprio script e explicadas em
[06-armadilhas.md](06-armadilhas.md).

---

## Os pontos de enxerto no jogo

Três funções originais são desviadas para código novo. Todas pela mesma técnica:
sobrescrever o início da função com `ldr r3, =alvo+1 / bx r3`, mantendo o tamanho
(`bl` não alcança os ~32 MB até o código novo).

| função original | vira | papel |
|---|---|---|
| `sub_08001F14` | `PtBrRenderizaTexto` | renderiza a linha de texto |
| `sub_08003BC0` / `sub_08003EB8` | `PtBrBlitEAvanca` | desenha um glifo e devolve o avanço |
| `sub_0800B130` | `PtBrMedeTexto` | mede a largura do texto |

O renderizador não é escrito à mão: `gerar_renderer_vwf.py` **copia** a função
original do assembly e aplica transformações identificadas por padrão. Rodar de
novo e comparar é uma forma de auditoria.

Além dos desvios, `patch_vwf.py` faz sete alterações no lugar — conversões de
unidade em consumidores que passaram a receber pixels onde antes recebiam
contagem de caracteres. Cada uma está comentada no script com o motivo.

---

## Por que o medidor também precisou mudar

Este é o ponto menos óbvio da arquitetura.

Converter só o renderizador quebra o jogo de um jeito silencioso: o texto encolhe
mas as **janelas continuam sendo dimensionadas** a 12px por caractere, porque
quem as dimensiona é outra função — `sub_0800B130`, que conta caracteres.

Com o VWF, contar caractere deixou de equivaler a medir largura. `PtBrMedeTexto`
percorre o texto igual à original (inclusive expandindo os códigos de
substituição de nomes) mas somando larguras reais, e devolve **na mesma unidade
do original** — quantas células de 12px o texto ocupa. Assim os 12 chamadores
continuam intactos e as contas deles passam a dar certo sozinhas.

Detalhes em [03-geometria-menus.md](03-geometria-menus.md).

---

## O que fica em cada lugar

| caminho | conteúdo |
|---|---|
| `src/ptbr_blit.c` | desenha um glifo: largura variável, recuo, sombra, cores |
| `src/ptbr_render.c` | cola: lê a tabela de larguras, chama o desenhador |
| `src/ptbr_medidor.c` | mede o texto para o dimensionamento de janelas |
| `data/ptbr*.s` | **gerado** — strings, tabela de larguras, renderizador |
| `tools/csm3_text/` | todo o pipeline (extração, tradução, injeção, patches, verificação) |
| `build-ptbr.sh` | a ordem |
| `docs/` | o que foi descoberto |

Os `data/ptbr*.s` estão no `.gitignore`: são reproduzíveis, e versioná-los
convidaria alguém a editá-los à mão.
