# Observa o desenhador de fonte rodando de verdade, no mGBA.
#
# Tres tentativas de VWF falharam porque eu deduzia o comportamento. Aqui o
# jogo roda e eu leio o estado real: o que ha no buffer antes do glifo, o que
# ha depois, e de onde vem o fundo da caixa de dialogo.

set pagination off
set confirm off
set architecture armv4t

target remote 192.168.80.1:2345

# sub_08003BC0 = desenhador de glifo, fase 0
break *0x08003BC0

printf "\n=== aguardando o jogo desenhar texto ===\n"
continue

printf "\n=== PARADO NO DESENHADOR ===\n"
printf "r0 (glifo)  = 0x%08X\n", $r0
printf "r1 (destino)= 0x%08X\n", $r1
printf "r2          = 0x%08X\n", $r2
printf "r3 (estilo) = 0x%08X\n", $r3

printf "\n--- buffer ANTES (64 bytes a partir do destino) ---\n"
x/16xw $r1

printf "\n--- o que ha ANTES do destino (revela se o buffer e compartilhado) ---\n"
x/8xw $r1-32

# Executa ate voltar da funcao
finish

printf "\n--- buffer DEPOIS ---\n"
x/16xw $r1

printf "\n=== fim ===\n"
