"""1) Testa a hipotese 'todas as ocorrencias dos opcodes 0x02xx sao operandos'.
   2) Dump das ocorrencias aceitas de 0x0218.
   3) Teste de encadeamento: parseando a partir de uma ocorrencia aceita,
      caimos em outra ocorrencia aceita do mesmo opcode? (evidencia de fronteira)
"""
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


def parse_expr(body, off):
    depth = 0
    while True:
        if off + 2 > len(body):
            raise Bad('eof')
        tok = struct.unpack_from('<H', body, off)[0]
        off += 2
        if tok == 0:
            if depth != 1:
                raise Bad('depth')
            return off
        if tok not in KNOWN:
            raise Bad('tok')
        if tok in PUSH_IMM:
            off += 2
            depth += 1
        elif tok in UNARY:
            depth = depth - 1 + 1 if depth >= 1 else (_ for _ in ()).throw(Bad('u'))
        elif tok in BINARY:
            if depth < 2:
                raise Bad('under')
            depth -= 1


print('=== 1) os 0x02xx sao precedidos por token de push (1/2/3)? ===')
for op in (0x0215, 0x0218, 0x0219, 0x0221, 0x0222):
    prev = collections.Counter()
    nxt = collections.Counter()
    tot = 0
    for s in scripts:
        body = bytes(s.body)
        for off in range(0, len(body) - 1, 2):
            if struct.unpack_from('<H', body, off)[0] != op:
                continue
            tot += 1
            if off >= 2:
                prev[struct.unpack_from('<H', body, off - 2)[0]] += 1
            if off + 4 <= len(body):
                nxt[struct.unpack_from('<H', body, off + 2)[0]] += 1
    as_operand = sum(v for k, v in prev.items() if k in PUSH_IMM)
    print(f'  0x{op:04X}: total={tot}  precedido por token 1/2/3 = {as_operand}/{tot}'
          f'  ({100.0*as_operand/tot:.0f}%)')
    print(f'     anteriores mais comuns: {prev.most_common(4)}')
    print(f'     seguintes  mais comuns: {nxt.most_common(4)}')

print('\n=== 2) ocorrencias de 0x0218 que passam no filtro estrito ===')
for s in scripts:
    body = bytes(s.body)
    for off in range(0, len(body) - 1, 2):
        if struct.unpack_from('<H', body, off)[0] != 0x0218:
            continue
        try:
            p = parse_expr(body, off + 2)
        except Bad:
            continue
        lo = max(0, off - 6)
        words = [struct.unpack_from('<H', body, x)[0]
                 for x in range(lo, min(len(body) - 1, p + 6), 2)]
        mk = (off - lo) // 2
        end = (p - lo) // 2
        out = []
        for i, w in enumerate(words):
            if i == mk:
                out.append('[%04X]' % w)
            elif mk < i < end:
                out.append('<%04X>' % w)
            else:
                out.append('%04X' % w)
        print(f'  script {s.index} @0x{off:04X} n={(p-off-2)//2}: {" ".join(out)}')

print('\n=== 3) encadeamento dos opcodes 0x04xx (evidencia de fronteira real) ===')
for op, n in ((0x0479, 3), (0x0480, 4), (0x0478, 2), (0x047A, 3)):
    hits = []
    for s in scripts:
        body = bytes(s.body)
        for off in range(0, len(body) - 1, 2):
            if struct.unpack_from('<H', body, off)[0] != op:
                continue
            try:
                p = off + 2
                for _ in range(n):
                    p = parse_expr(body, p)
            except Bad:
                continue
            hits.append((s.index, off, p, bytes(body)))
    chain = sum(1 for (si, o, p, b) in hits
                if p + 2 <= len(b) and struct.unpack_from('<H', b, p)[0] == op)
    nextops = collections.Counter()
    for (si, o, p, b) in hits:
        if p + 2 <= len(b):
            nextops[struct.unpack_from('<H', b, p)[0]] += 1
    print(f'  0x{op:04X}: aceitos={len(hits)}  '
          f'seguidos imediatamente pelo MESMO opcode={chain}')
    print(f'     opcodes seguintes mais comuns: {nextops.most_common(5)}')
