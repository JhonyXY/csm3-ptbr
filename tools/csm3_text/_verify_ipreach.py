import re, os, sys, collections

ROOT = "/home/jhony/decomps/csm3"

func_body = {}      # name -> list of (file,lineno,text)

# ---- Parse asm functions ----
for fn in sorted(os.listdir(os.path.join(ROOT, "asm"))):
    if not fn.endswith(".s"):
        continue
    path = os.path.join(ROOT, "asm", fn)
    cur = None
    with open(path, errors="replace") as f:
        for i, line in enumerate(f, 1):
            m = re.match(r"\s*(?:thumb|arm)_func_start\s+(\S+)", line)
            if m:
                cur = m.group(1)
                func_body.setdefault(cur, [])
                continue
            if cur is not None:
                func_body[cur].append((fn, i, line.rstrip()))

# ---- Parse C functions (brace matching) ----
for fn in sorted(os.listdir(os.path.join(ROOT, "src"))):
    if not fn.endswith(".c"):
        continue
    path = os.path.join(ROOT, "src", fn)
    with open(path, errors="replace") as f:
        lines = f.readlines()
    cur = None
    depth = 0
    started = False
    for i, line in enumerate(lines, 1):
        if cur is None:
            m = re.match(r"^[A-Za-z_].*?\b(\w+)\s*\(", line)
            if m and not line.strip().endswith(";"):
                cur = m.group(1)
                func_body.setdefault(cur, [])
                func_body[cur].append((fn, i, line.rstrip()))
                depth = line.count("{") - line.count("}")
                started = "{" in line
                if started and depth <= 0:
                    cur = None
        else:
            func_body[cur].append((fn, i, line.rstrip()))
            if "{" in line:
                started = True
            depth += line.count("{") - line.count("}")
            if started and depth <= 0:
                cur = None

CALL_RE = re.compile(r"\bbl\s+(\w+)")
CCALL_RE = re.compile(r"\b(sub_[0-9A-Fa-f]{8})\s*\(")

def callees(name):
    out = set()
    for (f, i, t) in func_body.get(name, []):
        for m in CALL_RE.finditer(t):
            out.add(m.group(1))
        for m in CCALL_RE.finditer(t):
            out.add(m.group(1))
    return out

IP_SYMS = ["gUnk_03006574", "sub_08012EA0", "sub_08012EE0", "sub_08012EF4",
           "sub_08012EC4", "sub_08012578"]

def direct_ip_hits(name):
    hits = []
    for (f, i, t) in func_body.get(name, []):
        for s in IP_SYMS:
            if s in t and name != s:
                hits.append((s, f, i, t.strip()))
    return hits

def analyze(root):
    seen = set()
    stack = [(root, [])]
    found = []
    unknown = set()
    while stack:
        fn, path = stack.pop()
        if fn in seen:
            continue
        seen.add(fn)
        if fn not in func_body:
            unknown.add(fn)
            continue
        for h in direct_ip_hits(fn):
            found.append((fn, path, h))
        if fn == "sub_08012578":
            continue
        for c in callees(fn):
            stack.append((c, path + [fn]))
    return found, seen, unknown

targets = ["sub_0806F6C4", "sub_0808F0C0", "sub_0808F474", "sub_0808F4B0",
           "sub_08093648", "sub_080936A8"]
if len(sys.argv) > 1:
    targets = sys.argv[1:]

for h in targets:
    found, seen, unknown = analyze(h)
    print("=" * 74)
    print("%s   reachable=%d  unresolved=%d" % (h, len(seen), len(unknown)))
    if unknown:
        print("  UNRESOLVED:", sorted(unknown))
    if not found:
        print("  NO IP REFERENCES ANYWHERE IN TRANSITIVE CLOSURE")
    for fn, path, (sym, f, i, t) in found:
        print("  HIT %-16s in %-16s via %s" % (sym, fn, "->".join(path[1:]) or "DIRECT"))
        print("       %s:%d  %s" % (f, i, t))
