#!/bin/bash
# Roda o tradutor nas 21.062 falas, com log.
#
# Existe como ARQUIVO porque passar a linha de comando por wsl.exe embaralha as
# aspas e o redirecionamento - o processo morria antes de criar o log.
cd /home/jhony/decomps/csm3/tools/csm3_text || exit 1
echo "inicio: $(date)" > _out/tradutor.log
exec python3 -u tradutor.py \
    --capacidade 78 \
    --lote 12 \
    --saida traducao.json >> _out/tradutor.log 2>&1
