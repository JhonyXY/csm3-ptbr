#!/bin/bash
# Commita e publica o estado atual no fork.
#
# Reverte os arquivos do upstream antes de commitar: eles sao saida de script e
# nao entram no repositorio. Reconstroi depois, para a arvore de trabalho ficar
# utilizavel.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1

# A mensagem vem de um arquivo: passar texto longo pela linha de comando atraves
# do wsl.exe embaralha as aspas.
ARQUIVO_MSG="${1:-.commit-msg.txt}"
if [ ! -f "$ARQUIVO_MSG" ]; then
    echo "ERRO: falta $ARQUIVO_MSG com a mensagem do commit" >&2
    exit 1
fi

echo "=== normalizando fim de linha ==="
for f in README-PTBR.md build-ptbr.sh docs/*.md .gitignore \
         tools/csm3_text/*.py tools/csm3_text/*.sh tools/csm3_text/*.md \
         src/ptbr_*.c; do
    [ -f "$f" ] && sed -i 's/\r$//' "$f"
done
chmod +x build-ptbr.sh tools/csm3_text/*.sh 2>/dev/null

echo "=== revertendo os arquivos do upstream ==="
./build-ptbr.sh --reverter >/dev/null 2>&1

echo "=== estado ==="
git add -A
echo "  arquivos no stage: $(git diff --cached --name-only | wc -l)"
echo "  do upstream modificados (so .gitignore e esperado):"
git diff --cached --name-only --diff-filter=M | sed 's/^/    /'

if git diff --cached --quiet; then
    echo "  nada a commitar"
    exit 0
fi

{ cat "$ARQUIVO_MSG"
  echo
  echo "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
} | git commit -q -F -

echo
echo "=== commit ==="
git log --oneline -1
git show --stat --oneline HEAD | tail -3

echo
echo "=== enviando para o fork ==="
GCM='/mnt/c/Program Files/Git/mingw64/bin/git-credential-manager.exe'
if [ -x "$GCM" ]; then
    git config --local credential.helper "\"$GCM\""
fi
git push fork ptbr 2>&1 | tail -6
