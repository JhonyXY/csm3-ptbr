"""Constroi o grafo de chamadas a partir do asm e verifica, para cada handler,
se algum callee (transitivo) toca o IP (gUnk_03006574) ou os helpers de IP."""
import re, sys, glob, collections

FUNCS = {}          # name -> list of body lines
ORDER = []

for path in sorted(glob.glob('/home/jhony/decomps/csm3/asm/**/*.s', recursive=True)):
    cur = None
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'\s*thumb_func_start\s+(\S+)', line)
        if m:
            cur = m.group(1)
            FUNCS.setdefault(cur, [])
            ORDER.append(cur)
            continue
        m2 = re.match(r'\s*arm_func_start\s+(\S+)', line)
        if m2:
            cur = m2.group(1)
            FUNCS.setdefault(cur, [])
            ORDER.append(cur)
            continue
        if cur is not None:
            FUNCS[cur].append(line)

CALLS = {}
TOUCHES_IP = set()
for name, body in FUNCS.items():
    text = ''.join(body)
    callees = set(re.findall(r'\bbl\s+(\w+)', text))
    # tail-calls / indirect via ldr pc ou bx rX apos ldr =func
    callees |= set(re.findall(r'\.4byte\s+(sub_[0-9A-Fa-f]+)', text))
    CALLS[name] = callees
    if 'gUnk_03006574' in text:
        TOUCHES_IP.add(name)

IPFUNCS = {'sub_08012EA0', 'sub_08012EC4', 'sub_08012EE0', 'sub_08012EF4', 'sub_08012578'}

def reach(root, maxdepth=12):
    seen, stack, hits = set(), [(root, 0)], []
    while stack:
        f, d = stack.pop()
        if f in seen or d > maxdepth:
            continue
        seen.add(f)
        if f in TOUCHES_IP or f in IPFUNCS:
            hits.append((f, d))
        for c in CALLS.get(f, ()):
            stack.append((c, d + 1))
    return seen, hits

HANDLERS = ['sub_0805B4B8','sub_0805B50C','sub_0805B564','sub_0805B5E8','sub_0805B63C',
            'sub_080604C8','sub_0806055C','sub_080607C4','sub_080607F4']

for h in HANDLERS:
    if h not in FUNCS:
        print(f'{h}: NAO ENCONTRADO NO ASM (talvez decompilado em C)')
        continue
    seen, hits = reach(h)
    direct = sorted(CALLS.get(h, ()))
    print(f'\n### {h}  (callees diretos: {direct})')
    print(f'    alcance transitivo: {len(seen)} funcoes')
    for f, d in sorted(hits, key=lambda x: x[1]):
        why = 'IP-helper' if f in IPFUNCS else 'ref gUnk_03006574'
        print(f'    !! depth={d} {f}  [{why}]')
