"""Verificacao independente do consumo de operandos dos handlers que chamam
sub_08012578.

Gramatica extraida DIRETAMENTE de asm/code_080123E4.s:212-538:

  loop:
    tok = u16[ip]; ip += 2
    if tok == 0:            return            # terminador, JA consumido
    if tok <= 0x7F:
        if tok in (1,2,3):  u16[ip]; ip += 2  # empurra 1 valor (le 1 palavra extra)
        else:               pass              # 0x04..0x7F: nao le, nao empurra (degenerado)
    else:
        if tok in (0x80,0x81):  pass          # unario: pop1/push1
        elif 0x82 <= tok <= 0x91: pass        # binario: pop2/push1
        else: pass                            # >0x91: degenerado (pop2, push lixo)
    goto loop

Portanto: minimo 1 palavra (terminador imediato), canonico 3 (tok=1, valor, 0x0000).
"""
from __future__ import annotations

import collections
import struct
import sys

sys.path.insert(0, '/home/jhony/decomps/csm3/tools/csm3_text')

import csm3rom

ROM = csm3rom.load_rom('/home/jhony/decomps/csm3/baserom.gba')

PUSH_IMM = {1, 2, 3}
UNARY = {0x80, 0x81}
BINARY = set(range(0x82, 0x92))


class Bad(Exception):
    pass


def parse_expr(body: bytes, off: int, strict: bool):
    """Consome UMA expressao. Devolve o novo offset.

    strict=True exige boa formacao RPN (so tokens conhecidos, profundidade de
    pilha coerente, resultado final com exatamente 1 valor).
    """
    depth = 0
    start = off
    while True:
        if off + 2 > len(body):
            raise Bad('fim do blob')
        tok = struct.unpack_from('<H', body, off)[0]
        off += 2
        if tok == 0:
            if strict and depth != 1:
                raise Bad(f'pilha={depth} no fim (esperado 1)')
            return off
        if tok in PUSH_IMM:
            if off + 2 > len(body):
                raise Bad('fim do blob no imediato')
            off += 2
            depth += 1
        elif tok in UNARY:
            if strict and depth < 1:
                raise Bad('unario com pilha vazia')
            depth = max(depth - 1, 0) + 1
        elif tok in BINARY:
            if strict and depth < 2:
                raise Bad(f'binario com pilha={depth}')
            depth = max(depth - 2, 0) + 1
        else:
            if strict:
                raise Bad(f'token degenerado 0x{tok:04X}')
        if off - start > 512:
            raise Bad('expressao longa demais')


def plausible_opcode(w: int) -> bool:
    return (w >> 8) <= 0x04


HANDLERS = [
    ('0805B4B8', 0x0215, 1),
    ('0805B50C', 0x0218, 1),
    ('0805B564', 0x0219, 5),
    ('0805B5E8', 0x0221, 4),
    ('0805B63C', 0x0222, 2),
    ('080604C8', 0x0479, 3),
    ('0806055C', 0x0480, 4),
    ('080607C4', 0x0478, 2),
    ('080607F4', 0x047A, 3),
]

scripts = [s for s in csm3rom.iter_scripts(ROM) if s is not None]
print(f'scripts carregados: {len(scripts)}\n')


def scan(opcode: int, ncalls: int, strict: bool):
    dist = collections.Counter()
    fails = 0
    total = 0
    for s in scripts:
        body = bytes(s.body)
        for off in range(0, len(body) - 1, 2):
            if struct.unpack_from('<H', body, off)[0] != opcode:
                continue
            total += 1
            p = off + 2
            try:
                for _ in range(ncalls):
                    p = parse_expr(body, p, strict)
            except Bad:
                fails += 1
                continue
            if p + 2 <= len(body):
                nxt = struct.unpack_from('<H', body, p)[0]
                if not plausible_opcode(nxt):
                    fails += 1
                    continue
            dist[(p - (off + 2)) // 2] += 1
    return dist, fails, total


for name, opcode, ncalls in HANDLERS:
    d_loose, f_loose, tot = scan(opcode, ncalls, strict=False)
    d_strict, f_strict, _ = scan(opcode, ncalls, strict=True)
    print(f'=== {name}  opcode=0x{opcode:04X}  chamadas={ncalls}  canonico={3*ncalls} ===')
    print(f'  ocorrencias brutas do padrao de bits: {tot}')
    print(f'  LOOSE  (sem validar RPN): aceitos={sum(d_loose.values())} rejeitados={f_loose}')
    print(f'         dist: {sorted(d_loose.items(), key=lambda x: -x[1])[:8]}')
    print(f'  STRICT (RPN bem formado): aceitos={sum(d_strict.values())} rejeitados={f_strict}')
    print(f'         dist: {sorted(d_strict.items(), key=lambda x: -x[1])[:8]}')
    print()
