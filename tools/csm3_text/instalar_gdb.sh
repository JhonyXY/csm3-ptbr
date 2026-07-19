#!/bin/bash
# Instala o depurador ARM. Necessario para instrumentar o blitter no mGBA em
# vez de continuar deduzindo o comportamento dele lendo assembly - foi essa
# deducao que me fez errar o VWF duas vezes.
export DEBIAN_FRONTEND=noninteractive

echo "=== atualizando indice de pacotes ==="
echo 1234 | sudo -S apt-get update -qq 2>&1 | tail -3

echo
echo "=== instalando gdb-multiarch ==="
echo 1234 | sudo -S apt-get install -y -qq gdb-multiarch 2>&1 | tail -8

echo
echo "=== verificando ==="
if command -v gdb-multiarch > /dev/null; then
  gdb-multiarch --version | head -1
  echo "  OK"
else
  echo "  gdb-multiarch: NAO instalou"
fi
