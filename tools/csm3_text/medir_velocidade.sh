#!/bin/bash
# Mede o throughput em lotes de tamanhos diferentes. Geracao e o gargalo, e
# lote maior amortiza o prompt de sistema e o glossario entre mais falas.
cd /home/jhony/decomps/csm3/tools/csm3_text || exit 1

for L in 5 12 20; do
  rm -f _out/vel.json
  echo "### lote de $L falas por requisicao ###"
  INICIO=$(date +%s)
  timeout 1200 python3 tradutor.py --limite 40 --lote "$L" --capacidade 78 \
    --saida vel.json > /tmp/vel.log 2>&1
  FIM=$(date +%s)
  DUR=$((FIM - INICIO))
  FEITAS=$(python3 -c "
import json
d = json.load(open('_out/vel.json'))
print(sum(1 for t in d['traducoes'] if t.get('pt')))
" 2>/dev/null || echo 0)
  if [ "$DUR" -gt 0 ] && [ "$FEITAS" -gt 0 ]; then
    TAXA=$(python3 -c "print(f'{$FEITAS/$DUR:.2f}')")
    HORAS=$(python3 -c "print(f'{15332/($FEITAS/$DUR)/3600:.1f}')")
    echo "  $FEITAS falas em ${DUR}s = $TAXA falas/s  ->  15.332 levariam ${HORAS}h"
  else
    echo "  falhou (ver /tmp/vel.log)"
  fi
  echo
done
