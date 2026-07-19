#!/usr/bin/env python3
"""Extrai o corpo em assembly (ou C) de cada handler de opcode.

Gera _out/handlers/<addr>.txt com o codigo do handler e os opcodes que apontam
para ele, para que a analise de quantos operandos cada opcode consome possa ser
feita sobre um material limpo.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).parent / "_out"
HANDLER_DIR = OUT_DIR / "handlers"

FUNC_START = re.compile(r"^\s*(?:thumb|arm)_func_start\s+(\S+)")
C_FUNC = re.compile(r"^\w[\w\s\*]*?\b(sub_[0-9A-Fa-f]{8})\s*\(")


def index_asm() -> dict[str, tuple[Path, int, int]]:
    """Mapeia nome da funcao -> (arquivo, linha inicial, linha final)."""
    index: dict[str, tuple[Path, int, int]] = {}
    for path in sorted((ROOT / "asm").glob("*.s")):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        starts: list[tuple[int, str]] = []
        for i, line in enumerate(lines):
            m = FUNC_START.match(line)
            if m:
                starts.append((i, m.group(1)))
        for j, (line_no, name) in enumerate(starts):
            end = starts[j + 1][0] if j + 1 < len(starts) else len(lines)
            index[name] = (path, line_no, end)
    return index


def index_c() -> dict[str, tuple[Path, int, int]]:
    """Mapeia funcoes ja decompiladas em src/*.c."""
    index: dict[str, tuple[Path, int, int]] = {}
    for path in sorted((ROOT / "src").glob("*.c")):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        starts: list[tuple[int, str]] = []
        for i, line in enumerate(lines):
            m = C_FUNC.match(line)
            if m:
                starts.append((i, m.group(1)))
        for j, (line_no, name) in enumerate(starts):
            end = starts[j + 1][0] if j + 1 < len(starts) else len(lines)
            index[name] = (path, line_no, end)
    return index


def main() -> int:
    handlers_path = OUT_DIR / "handlers.json"
    if not handlers_path.exists():
        print("rode survey.py primeiro", file=sys.stderr)
        return 1

    handlers: dict[str, list[str]] = json.loads(handlers_path.read_text("utf-8"))
    asm_idx = index_asm()
    c_idx = index_c()

    HANDLER_DIR.mkdir(parents=True, exist_ok=True)
    for old in HANDLER_DIR.glob("*.txt"):
        old.unlink()

    found_asm = found_c = missing = 0
    manifest = []

    for addr_str, opcodes in sorted(handlers.items()):
        addr = int(addr_str, 16)
        name = f"sub_{addr:08X}"
        # Os simbolos no repo usam hex minusculo depois do prefixo.
        candidates = [name, f"sub_{addr:08x}"]

        src = None
        kind = None
        for cand in candidates:
            if cand in asm_idx:
                src, kind = asm_idx[cand], "asm"
                break
            if cand in c_idx:
                src, kind = c_idx[cand], "c"
                break

        if src is None:
            missing += 1
            manifest.append({"addr": addr_str, "opcodes": opcodes, "status": "missing"})
            continue

        path, start, end = src
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        body = "\n".join(lines[start:end]).rstrip()

        if kind == "asm":
            found_asm += 1
        else:
            found_c += 1

        rel = path.relative_to(ROOT)
        out = HANDLER_DIR / f"{addr:08X}.txt"
        out.write_text(
            f"# handler {addr_str}  ({kind})\n"
            f"# fonte: {rel}:{start + 1}-{end}\n"
            f"# opcodes que apontam para ele: {', '.join(opcodes)}\n"
            f"# linhas: {end - start}\n"
            f"\n{body}\n",
            encoding="utf-8",
        )
        manifest.append(
            {
                "addr": addr_str,
                "opcodes": opcodes,
                "status": kind,
                "source": f"{rel}:{start + 1}",
                "lines": end - start,
                "file": str(out.relative_to(Path(__file__).parent)),
            }
        )

    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"handlers em asm : {found_asm}")
    print(f"handlers em C   : {found_c}")
    print(f"nao encontrados : {missing}")
    print(f"saida           : {HANDLER_DIR}")

    sizes = sorted(m["lines"] for m in manifest if m.get("lines"))
    if sizes:
        print(
            f"tamanho (linhas): min {sizes[0]} / mediana {sizes[len(sizes)//2]} "
            f"/ max {sizes[-1]} / total {sum(sizes):,}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
