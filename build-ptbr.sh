#!/bin/bash
#
# Constroi a ROM em portugues do Brasil.
#
#     ./build-ptbr.sh              constroi
#     ./build-ptbr.sh --reverter   desfaz tudo e volta ao decomp original
#
# A ORDEM AQUI NAO E ARBITRARIA. Cada passo depende do anterior de um jeito que
# nao e obvio, e trocar dois de lugar produz erro SILENCIOSO - a build sai, roda,
# e esta errada. Este arquivo existe para que ninguem (inclusive nos) precise
# lembrar disso de novo. As dependencias reais:
#
#   1. patch_acentos --so-mapa  ANTES de migrar_para_build
#      encoder.py le _out/acentos_mapa.json para converter 'a com til' no codigo
#      do jogo. Sem o arquivo ele cai em strip_accents() e grava "Nao" sem til,
#      sem avisar. Como migrar_para_build tem que rodar antes do patch_acentos
#      completo (os dois editam data1.s e cada um guarda o proprio backup), o
#      mapa precisa ser calculado a parte, antes de tudo.
#
#   2. migrar_para_build  ANTES de patch_acentos
#      Ordem imposta pelos backups: patch_acentos guarda data1.s.pre-acentos e
#      migrar_para_build guarda data1.s.pre-ptbr. Invertendo, um revert desfaz o
#      trabalho do outro.
#
#   3. gerar_larguras  DEPOIS de patch_acentos
#      A tabela de larguras mede os glifos ACENTUADOS, que patch_acentos compoe.
#      Medindo antes, ela pega o simbolo que ocupava o slot na baserom, e o
#      desenhador comeca a pintar o acento na coluna errada, cortando o til.
#
#   4. gerar_larguras  DEPOIS de patch_vwf --reverter
#      O revert do VWF apaga os arquivos gerados, inclusive ptbr_larguras.s.
#      Gerar antes do revert e perder o arquivo e o build falhar no linker.
#
# Requisitos: baserom.gba na raiz, DEVKITARM apontando para o toolchain.

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FERRAMENTAS="$RAIZ/tools/csm3_text"
cd "$RAIZ"

: "${DEVKITARM:=$HOME/devkitARM}"
export DEVKITARM

passo() { printf '\n\033[1m>>> %s\033[0m\n' "$*"; }

if [[ "${1:-}" == "--reverter" ]]; then
    passo "Desfazendo os patches"
    python3 "$FERRAMENTAS/patch_vwf.py" --reverter
    python3 "$FERRAMENTAS/patch_acentos.py" --reverter
    python3 "$FERRAMENTAS/migrar_para_build.py" --reverter
    echo
    echo "Repositorio de volta ao decomp original. 'make' constroi a ROM japonesa."
    exit 0
fi

if [[ ! -f baserom.gba ]]; then
    echo "ERRO: falta baserom.gba na raiz do repositorio." >&2
    echo "      sha1 esperado: 3f5253fcf57e07ce52472bd29a61d16b98a12376" >&2
    exit 1
fi

# Estado limpo antes de comecar: os patches nao sao idempotentes, eles procuram
# padroes exatos no assembly e falham se ja estiverem aplicados.
passo "Limpando patches anteriores"
python3 "$FERRAMENTAS/patch_vwf.py" --reverter    >/dev/null 2>&1 || true
python3 "$FERRAMENTAS/patch_acentos.py" --reverter >/dev/null 2>&1 || true
python3 "$FERRAMENTAS/migrar_para_build.py" --reverter >/dev/null 2>&1 || true

passo "1/7  Alocando os glifos acentuados (so o mapa)"
python3 "$FERRAMENTAS/patch_acentos.py" --so-mapa

passo "2/7  Injetando as strings de sistema traduzidas"
python3 "$FERRAMENTAS/migrar_para_build.py"

passo "3/7  Gravando os bitmaps das acentuadas na fonte"
python3 "$FERRAMENTAS/patch_acentos.py"

passo "4/7  Medindo a largura de cada glifo (VWF)"
python3 "$FERRAMENTAS/gerar_larguras.py"

passo "5/7  Gerando o renderizador de largura variavel"
python3 "$FERRAMENTAS/gerar_renderer_vwf.py"

passo "6/7  Aplicando os patches de VWF no assembly"
python3 "$FERRAMENTAS/patch_vwf.py"

passo "7/7  Compilando"
rm -f csm3.gba csm3.elf
make -j"$(nproc)"

passo "Conferindo que nada deslocou na ROM"
python3 "$FERRAMENTAS/verificar_vwf.py" | sed -n '/VEREDITO/,+4p'

echo
echo "ROM pronta: $RAIZ/csm3.gba"
sha1sum csm3.gba
