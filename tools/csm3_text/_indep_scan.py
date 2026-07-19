"""Verificacao independente: parser de expressao derivado direto de sub_08012578.

Gramatica confirmada lendo asm/code_080123E4.s:212-538:
  loop:
    tok = read_u16(); IP += 2
    if tok == 0:            -> FIM da expressao (r8=1, sai do loop)
    elif tok in (1,2,3):    -> le MAIS uma palavra (imediato / id de variavel), push
    elif tok <= 0x7F:       -> nada (cai em _080127CC sem push)
    elif tok in (0x80,0x81) -> unario: pop1 push1
    else (>= 0x82)          -> binario: pop2 push1
  retorna stack[0]
"""
from __future__ import annotations
import struct, collections, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import csm3rom

ROM = Path('/home/jhony/decomps/csm3/baserom.gba').read_bytes()


def parse_expr(buf, pos):
    """Retorna (novo_pos, depth_final, ok). ok=False se estourou o buffer."""
    depth = 0
    steps = 0
    while True:
        if pos + 2 > len(buf):
            return pos, depth, False
        tok = struct.unpack_from('<H', buf, pos)[0]
        pos += 2
        steps += 1
        if steps > 256:
            return pos, depth, False
        if tok == 0:
            return pos, depth, True
        if tok in (1, 2, 3):
            if pos + 2 > len(buf):
                return pos, depth, False
            pos += 2
            depth += 1
        elif tok <= 0x7F:
            pass
        elif tok <= 0x81:
            if depth < 1:
                return pos, depth, False
            # pop1 push1 -> depth inalterado
        else:
            if depth < 2:
                return pos, depth, False
            depth -= 1


TARGETS = {
    0x037C: ('sub_0806F6C4', 1),
    0x0353: ('sub_0808F0C0', 1),
    0x0350: ('sub_0808F474', 2),
    0x0354: ('sub_0808F4B0', 2),
    0x035B: ('sub_08093648', 1),
    0x035E: ('sub_080936A8', 1),
}

rom = ROM
blobs = []
for sc in csm3rom.iter_scripts(rom):
    blobs.append((sc.index, bytes(sc.body)))

print("blobs de script (PSI3): %d" % len(blobs))

stats = {op: collections.Counter() for op in TARGETS}
strict = {op: collections.Counter() for op in TARGETS}
total = {op: 0 for op in TARGETS}

for idx, data in blobs:
    body = data
    for pos in range(0, len(body) - 1, 2):
        w = struct.unpack_from('<H', body, pos)[0]
        if w not in TARGETS:
            continue
        name, nexpr = TARGETS[w]
        total[w] += 1
        p = pos + 2
        ok_all = True
        depths = []
        for _ in range(nexpr):
            p, d, ok = parse_expr(body, p)
            depths.append(d)
            if not ok:
                ok_all = False
                break
        if not ok_all:
            continue
        words = (p - (pos + 2)) // 2
        stats[w][words] += 1
        # filtro estrito: cada expressao deve terminar com exatamente 1 valor
        if all(d == 1 for d in depths):
            strict[w][words] += 1

print()
for op in sorted(TARGETS):
    name, nexpr = TARGETS[op]
    print("=" * 66)
    print("op=0x%04X %s  (%d expressao(oes))  ocorrencias brutas=%d"
          % (op, name, nexpr, total[op]))
    a = stats[op]
    s = strict[op]
    print("  todas as que parseiam : %s" % sorted(a.items()))
    print("  stack-discipline ok   : %s" % sorted(s.items()))
    if s:
        mode = s.most_common(1)[0]
        print("  MODA (estrito) = %d palavras (n=%d de %d, %.0f%%)"
              % (mode[0], mode[1], sum(s.values()), 100.0 * mode[1] / sum(s.values())))
