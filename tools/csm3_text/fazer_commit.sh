#!/bin/bash
# Cria o branch da traducao e faz o commit inicial.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1

if ! git config user.email >/dev/null 2>&1; then
    git config user.email "pabloruanpnunes200@gmail.com"
    git config user.name "Jhony"
    echo "identidade do git configurada neste repositorio"
fi

git rev-parse --verify ptbr >/dev/null 2>&1 || git checkout -b ptbr
git checkout ptbr 2>/dev/null || true

git add -A

git commit --file=- <<'MENSAGEM'
Traducao PT-BR: motor de fonte de largura variavel e pipeline

Adiciona a base para traduzir o jogo para portugues do Brasil, construida
sobre o disassembly sem alterar nenhum arquivo do upstream a mao.

MOTOR DE FONTE (src/ptbr_*.c)

O jogo desenha todo caractere numa celula fixa de 12px - certo para japones,
desperdicio para o alfabeto latino. O VWF mede cada glifo e avanca so o
necessario: 8,34px de media, 30% de economia, que e o que permite o texto em
portugues caber nas caixas.

  ptbr_blit.c     desenha o glifo: largura e recuo variaveis, sombra, cores
  ptbr_render.c   cola entre o renderizador do jogo e o desenhador
  ptbr_medidor.c  mede o texto, alimentando o dimensionamento das janelas

O medidor existe porque converter so o renderizador quebra o jogo de forma
silenciosa: o texto encolhe mas as janelas continuam sendo dimensionadas a
12px por caractere, ja que quem as dimensiona e outra funcao.

ACENTUACAO

Os 25 glifos acentuados nao existem na fonte original. Sao compostos - letra
base mais acento - e gravados em slots que o texto japones nao referencia, com
o mapeamento Shift-JIS ajustado para alcanca-los.

PIPELINE (tools/csm3_text/)

Extracao, deduplicacao (27% das falas eram repeticao), traducao por modelo
local com validacao de genero e de codigos de controle, e reinjecao com
repointing automatico.

O formato do script foi provado por fechamento, nao por leitura: caminhar por
todo o bytecode e serializar de volta da 0 opcodes desconhecidos e 0 saltos
invalidos em 45.762 alvos.

RESTRICAO QUE ORIENTA TUDO

Os dados sao 32 MB de .incbin opaco com 102.100 ponteiros crus. Se qualquer
funcao existente mudar de tamanho, tudo depois dela desloca e esses ponteiros
apontam errado - sem erro de compilacao e sem aviso. Por isso todo patch em
codigo existente troca instrucoes mantendo a contagem, com nop onde a conta
encurtou, e codigo novo entra em objetos novos ligados no fim da secao rom.

verificar_vwf.py confere isso a cada build.

BUILD

  make               ROM japonesa original, byte a byte
  ./build-ptbr.sh    ROM em portugues

A ordem dos sete passos do build-ptbr.sh nao e arbitraria; trocar dois de
lugar produz erro silencioso. As dependencias estao comentadas no script.

DOCUMENTACAO

docs/ traz o que foi descoberto por engenharia reversa: o layout do buffer de
fonte, a geometria das janelas e do cursor, o formato do bytecode, o pipeline
de traducao, e as armadilhas que custaram caro.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
MENSAGEM

echo
echo "=== commit criado ==="
git log --oneline -1
git show --stat --oneline HEAD | tail -5
echo
echo "branch: $(git branch --show-current)"
