import struct, sys
import _verify_ipreach as c

rom = open('/home/jhony/decomps/csm3/baserom.gba','rb').read()

def table(off, size):
    out = []
    for i in range(0, size, 4):
        v = struct.unpack('<I', rom[off+i:off+i+4])[0]
        out.append(v)
    return out

targets = set()
for name, off in [('gUnk_08BCA098', 0xBCA098), ('gUnk_08BCA138', 0xBCA138)]:
    ptrs = table(off, 0xA0)
    print("== %s ==" % name)
    for i, p in enumerate(ptrs):
        fn = 'sub_%08X' % (p & ~1)
        known = fn in c.func_body
        print("  [%2d] %08X -> %s %s" % (i, p, fn, '' if known else '(UNKNOWN SYMBOL)'))
        targets.add(fn)

print("\n=== IP reachability of every indirect target ===")
any_hit = False
for fn in sorted(targets):
    if fn not in c.func_body:
        print("%-16s : NOT A KNOWN FUNCTION SYMBOL" % fn)
        continue
    found, seen, unknown = c.analyze(fn)
    hits = [h for h in found]
    if hits:
        any_hit = True
        print("%-16s : *** %d IP HIT(S) ***" % (fn, len(hits)))
        for f2, path, (sym, f3, i3, t3) in hits:
            print("     %s in %s (%s:%d)" % (sym, f2, f3, i3))
    else:
        print("%-16s : clean (reach=%d, unresolved=%s)" % (fn, len(seen), sorted(unknown) or 'none'))
print("\nANY IP CONTACT VIA INDIRECT TABLES:", any_hit)
