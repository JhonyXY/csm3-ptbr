#!/bin/bash
# Prepara o ambiente Python do WSL para falar com o llama-server do Windows.
# So precisa de httpx - nada de ML aqui, a GPU esta do outro lado.

cd /home/jhony/decomps/csm3/tools/csm3_text || exit 1

echo "=== httpx ==="
if python3 -c "import httpx" 2>/dev/null; then
  python3 -c "import httpx; print('  ja instalado:', httpx.__version__)"
else
  echo "  instalando..."
  pip install --quiet --break-system-packages httpx 2>&1 | tail -3
  python3 -c "import httpx; print('  instalado:', httpx.__version__)" 2>&1
fi

echo
echo "=== endereco que o runner vai usar ==="
python3 -c "import sys; sys.path.insert(0,'.'); import tradutor; print(' ', tradutor.SERVIDOR)"

echo
echo "=== o servidor responde nesse endereco? ==="
BASE=$(python3 -c "import sys; sys.path.insert(0,'.'); import tradutor; print(tradutor.SERVIDOR.rsplit('/v1',1)[0])")
if curl -s -m 10 "$BASE/health"; then echo "  OK"; else echo "  ainda nao"; fi
