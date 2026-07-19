#!/bin/bash
cd /home/jhony/decomps/csm3 || exit 1
F=asm/code_copy.s

for n in 4084 4150 4234 10680; do
  echo "=== largura da caixa, linha $n ==="
  sed -n "${n},$((n+7))p" "$F"
  echo
done

echo "=== chunking: decremento de 8, linhas 7178-7190 ==="
sed -n '7178,7190p' "$F"
echo
echo "=== chunking: resto, linhas 7232,7255 ==="
sed -n '7232,7255p' "$F"
