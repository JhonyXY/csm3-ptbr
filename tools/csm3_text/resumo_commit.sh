#!/bin/bash
# Resumo do que entraria no commit, para revisar antes de publicar.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1

git add -A

echo "=== arquivos no stage ==="
git diff --cached --name-only | wc -l

echo
echo "=== por area ==="
git diff --cached --name-only | awk -F/ '
  /^tools\/csm3_text\/_out/ {a["_out (texto e traducoes)"]++; next}
  /^tools\/csm3_text/       {a["tools/csm3_text (pipeline)"]++; next}
  /^docs/                   {a["docs"]++; next}
  /^src/                    {a["src (motor VWF)"]++; next}
  {a["raiz"]++}
  END {for (k in a) printf "  %-32s %4d\n", k, a[k]}'

echo
echo "=== tamanho total ==="
git diff --cached --name-only | tr '\n' '\0' | du -bc --files0-from=- 2>/dev/null \
  | tail -1 | awk '{printf "  %.1f MB\n", $1/1048576}'

echo
echo "=== os 10 maiores ==="
git diff --cached --name-only | tr '\n' '\0' | du -h --files0-from=- 2>/dev/null \
  | sort -rh | head -10 | sed 's/^/  /'

echo
echo "=== conferencia: nenhuma ROM, nenhum backup ==="
if git diff --cached --name-only | grep -qE '\.gba$|\.pre-(vwf|acentos|ptbr)$|baserom'; then
    echo "  ATENCAO: ha ROM ou backup no stage:"
    git diff --cached --name-only | grep -E '\.gba$|\.pre-|baserom' | sed 's/^/    /'
else
    echo "  ok - nenhuma ROM nem backup"
fi

echo
echo "=== arquivos do upstream modificados (deveria ser so .gitignore) ==="
git diff --cached --name-only --diff-filter=M | sed 's/^/  /'
