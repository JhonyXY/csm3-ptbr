import _verify_ipreach as c

names = ['sub_08012F0C','sub_08092D4C','sub_08093D28','sub_08092904',
         'sub_080639BC','sub_0806380C','sub_0800E77C','sub_08069884',
         'sub_0806EF98','sub_08069C54','sub_0806F0B4','sub_08004544',
         'sub_08011104','sub_0800480C','sub_0800471C']
print("--- body capture check ---")
for n in names:
    b = c.func_body.get(n)
    if b is None:
        print("%-16s MISSING" % n)
    else:
        print("%-16s lines=%-5d src=%s:%d" % (n, len(b), b[0][0], b[0][1]))

# does sub_08004544 (C) touch IP?
print("\n--- sub_08004544 IP hits ---")
print(c.direct_ip_hits('sub_08004544'))
print("callees:", sorted(c.callees('sub_08004544')))

# which reachable func in sub_0808F0C0 closure calls the indirect thunks?
print("\n--- who calls _call_via_* / sub_08004544 inside 0808F0C0 closure ---")
found, seen, unknown = c.analyze('sub_0808F0C0')
for fn in sorted(seen):
    cs = c.callees(fn)
    bad = cs & {'_call_via_r0', '_call_via_r8', 'sub_08004544', '__udivsi3'}
    if bad:
        print("%-16s -> %s" % (fn, sorted(bad)))
