#!/bin/bash
# O llama-server roda no Windows; o runner roda aqui no WSL. Precisa achar
# por qual endereco o WSL alcanca o servidor.

echo "=== via 127.0.0.1 (funciona se o WSL estiver em rede espelhada) ==="
if curl -s -m 8 http://127.0.0.1:8080/health; then echo "  OK"; else echo "  nao alcanca"; fi

HOSTIP=$(ip route show default | awk '{print $3}')
echo
echo "=== via IP do host Windows ($HOSTIP) ==="
if curl -s -m 8 "http://$HOSTIP:8080/health"; then echo "  OK"; else echo "  nao alcanca"; fi

echo
echo "=== IPs de nameserver (alternativa em WSL2 NAT) ==="
grep nameserver /etc/resolv.conf 2>/dev/null | awk '{print $2}' | while read -r ip; do
  printf '  %s: ' "$ip"
  if curl -s -m 5 "http://$ip:8080/health" > /dev/null 2>&1; then echo "OK"; else echo "nao"; fi
done
