"""Analise de sensibilidade do filtro estrito + inspecao dos bytes crus."""
from __future__ import annotations

import collections
import struct
import sys

sys.path.insert(0, '/home/jhony/decomps/csm3/tools/csm3_text')
import csm3rom

ROM = csm3rom.load_rom('/home/jhony/decomps/csm3/baserom.gba')
scripts = [s for s in csm3rom.iter_scripts(ROM) if s is not None]

PUSH_IMM = {1, 2, 3}
UNARY = {0x80, 0x81}
BINARY = set(range(0x82, 0x92))
KNOWN = {0} | PUSH_IMM | UNARY | BINARY


class Bad(Exception):
    pass


def parse_expr(body, off, mode):
    """mode: 'loose' | 'tokens' (so exige tokens conhecidos) | 'strict' (tokens+RPN)"""
    depth = 0
    start = off
    while True:
        if off + 2 > len(body):
            raise Bad('eof')
        tok = struct.unpack_from('<H', body, off)[0]
        off += 2
        if tok == 0:
            if mode == 'strict' and depth != 1:
                raise Bad(f'depth={depth}')
            return off
        if mode in ('tokens', 'strict') and tok not in KNOWN:
            raise Bad(f'tok 0x{tok:04X}')
        if tok in PUSH_IMM:
            off += 2
            depth += 1
        elif tok in UNARY:
            depth = max(depth - 1, 0) + 1
        elif tok in BINARY:
            if mode == 'strict' and depth < 2:
                raise Bad('underflow')
            depth = max(depth - 2, 0) + 1
        if off - start > 512:
            raise Bad('long')


HANDLERS = [('0805B4B8', 0x0215, 1), ('0805B50C', 0x0218, 1), ('0805B564', 0x0219, 5),
            ('0805B5E8', 0x0221, 4), ('0805B63C', 0x0222, 2), ('080604C8', 0x0479, 3),
            ('0806055C', 0x0480, 4), ('080607C4', 0x0478, 2), ('080607F4', 0x047A, 3)]


def scan(opcode, ncalls, mode, require_next=True):
    dist = collections.Counter()
    for s in scripts:
        body = bytes(s.body)
        for off in range(0, len(body) - 1, 2):
            if struct.unpack_from('<H', body, off)[0] != opcode:
                continue
            p = off + 2
            try:
                for _ in range(ncalls):
                    p = parse_expr(body, p, mode)
            except Bad:
                continue
            if require_next and p + 2 <= len(body):
                if (struct.unpack_from('<H', body, p)[0] >> 8) > 0x04:
                    continue
            dist[(p - (off + 2)) // 2] += 1
    return dist


print('=== sensibilidade: tokens-conhecidos vs RPN-estrito vs sem-filtro-de-proximo ===')
for name, op, n in HANDLERS:
    t = scan(op, n, 'tokens')
    s_ = scan(op, n, 'strict')
    s_nonext = scan(op, n, 'strict', require_next=False)
    print(f'{name} 0x{op:04X} n={n} canon={3*n}')
    print(f'   tokens-ok : {dict(sorted(t.items()))}')
    print(f'   strict    : {dict(sorted(s_.items()))}')
    print(f'   strict-sem-next: {dict(sorted(s_nonext.items()))}')

print('\n=== bytes crus em torno de cada ocorrencia dos opcodes raros ===')
for name, op, n in [('0805B4B8', 0x0215, 1), ('0805B564', 0x0219, 5),
                    ('0805B5E8', 0x0221, 4), ('0805B63C', 0x0222, 2)]:
    print(f'\n--- {name} opcode 0x{op:04X} ---')
    shown = 0
    for s in scripts:
        body = bytes(s.body)
        for off in range(0, len(body) - 1, 2):
            if struct.unpack_from('<H', body, off)[0] != op:
                continue
            if shown >= 6:
                break
            lo = max(0, off - 8)
            words = [struct.unpack_from('<H', body, x)[0]
                     for x in range(lo, min(len(body) - 1, off + 24), 2)]
            marker = (off - lo) // 2
            txt = ' '.join(('[%04X]' % w) if i == marker else ('%04X' % w)
                           for i, w in enumerate(words))
            print(f'  script {s.index} @0x{off:04X}: {txt}')
            shown += 1
        if shown >= 6:
            break
