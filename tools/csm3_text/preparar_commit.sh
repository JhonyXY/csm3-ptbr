#!/bin/bash
# Deixa a arvore pronta para o commit: normaliza fim de linha nos arquivos novos
# e devolve os arquivos do upstream ao estado original.
#
# Os arquivos do upstream sao saida de script - eles nao entram no commit. Quem
# clonar roda ./build-ptbr.sh e os regenera identicos.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1

echo "=== normalizando fim de linha ==="
for f in README-PTBR.md build-ptbr.sh docs/*.md .gitignore; do
    [ -f "$f" ] && sed -i 's/\r$//' "$f"
done
for f in tools/csm3_text/*.py tools/csm3_text/*.sh src/ptbr_*.c; do
    [ -f "$f" ] && sed -i 's/\r$//' "$f"
done
chmod +x build-ptbr.sh

echo "=== revertendo os arquivos do upstream ==="
./build-ptbr.sh --reverter 2>&1 | tail -4

echo
echo "=== estado do git ==="
echo "--- modificados (deveria estar vazio, fora .gitignore) ---"
git status --porcelain | grep '^ M' || echo "  (nenhum)"
echo "--- novos ---"
git status --porcelain | grep '^??' | sed 's/^?? /  /'
