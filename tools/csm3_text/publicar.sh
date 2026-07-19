#!/bin/bash
# Empurra o branch ptbr para o fork.
#
# O git do WSL nao tem credencial propria. Em vez de criar um token, usa o
# Git Credential Manager do Windows, que ja guarda a credencial do GitHub.
# A aspa simples no config e necessaria por causa do espaco em "Program Files".
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1

GCM='/mnt/c/Program Files/Git/mingw64/bin/git-credential-manager.exe'

if [ ! -x "$GCM" ]; then
    echo "ERRO: nao achei o Git Credential Manager em:" >&2
    echo "  $GCM" >&2
    exit 1
fi

# As aspas DENTRO do valor sao obrigatorias. Sem elas o git le o valor como
# "comando + argumentos" e tenta executar /mnt/c/Program passando
# "Files/Git/..." como parametro - o helper nunca roda e o git cai no prompt
# de usuario e senha.
git config --local credential.helper "\"$GCM\""
echo "helper: $(git config --local --get credential.helper)"
echo

echo "=== enviando o branch ptbr para o fork ==="
git push -u fork ptbr 2>&1 | tail -15
