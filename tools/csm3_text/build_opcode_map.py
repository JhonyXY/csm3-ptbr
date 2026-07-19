#!/usr/bin/env python3
"""Converte o resultado da analise dos handlers em _out/opcodes.json.

A analise devolveu, para cada handler, quantas palavras ele consome. O valor -1
e sentinela de TAMANHO VARIAVEL: esses handlers consomem expressoes RPN
auto-delimitadas (terminadas pelo token 0x0000) e/ou strings.

Este script consolida tudo e reporta o que ficou ambiguo.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

OUT_DIR = Path(__file__).parent / "_out"
RESULT_PATH = OUT_DIR / "workflow_result.json"
OPCODES_PATH = OUT_DIR / "opcodes.json"

OPCODE_RE = re.compile(r"hi=0x([0-9A-Fa-f]{2})\[0x([0-9A-Fa-f]{2})\]")

# Quantas expressoes RPN o handler consome, extraido da prosa do operand_note.
EXPR_WORDS = {
    "uma": 1, "um": 1, "1": 1,
    "duas": 2, "dois": 2, "2": 2,
    "tres": 3, "3": 3,
    "quatro": 4, "4": 4,
    "cinco": 5, "5": 5,
    "seis": 6, "6": 6,
    "sete": 7, "7": 7,
    "oito": 8, "8": 8,
    "nove": 9, "9": 9,
    "dez": 10, "10": 10,
}

EXPR_RE = re.compile(
    r"(\b(?:uma|um|duas|dois|tres|quatro|cinco|seis|sete|oito|nove|dez|\d+)\b)"
    r"\s+express",
    re.IGNORECASE,
)


def parse_opcodes(entries: list[str]) -> list[int]:
    out = []
    for e in entries or []:
        m = OPCODE_RE.search(e)
        if m:
            out.append((int(m.group(1), 16) << 8) | int(m.group(2), 16))
    return out


def infer_expressions(note: str) -> int | None:
    """Extrai da prosa quantas expressoes RPN o handler consome."""
    if not note:
        return None
    m = EXPR_RE.search(note)
    if not m:
        return None
    key = m.group(1).lower()
    return EXPR_WORDS.get(key, int(key) if key.isdigit() else None)


def main() -> int:
    if not RESULT_PATH.exists():
        print(f"ERRO: {RESULT_PATH} nao encontrado", file=sys.stderr)
        return 1

    raw = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    # O arquivo do workflow embrulha o retorno do script em "result".
    data = raw.get("result", raw)
    handlers = data.get("handlers", [])

    for line in raw.get("logs", []) or []:
        print(f"  log: {line}")

    print("=" * 72)
    print("RESULTADO DA ANALISE DOS HANDLERS")
    print("=" * 72)
    print(f"  handlers analisados : {len(handlers)}")
    print(f"  marcados como salto : {len(data.get('saltos', []))}")
    print(f"  marcados como texto : {len(data.get('texto', []))}")
    print(f"  confianca baixa     : {len(data.get('confianca_baixa', []))}")
    print(f"  candidatos extras   : {len(data.get('candidatos_extras', []))}")
    for nota in data.get("notas_completude", []) or []:
        print(f"      nota: {nota[:150]}")

    conf = Counter(h.get("confidence", "?") for h in handlers)
    print(f"  confianca: {dict(conf)}")

    opcodes: dict[str, dict] = {}
    variable = []
    conflicts = []
    unmapped = []

    for h in handlers:
        codes = parse_opcodes(h.get("opcodes"))
        if not codes:
            unmapped.append(h.get("addr"))
            continue

        words = h.get("operand_words", 0)
        note = h.get("operand_note", "") or ""
        is_var = words is not None and words < 0

        spec = {
            "addr": h.get("addr"),
            "operands": 0 if is_var else int(words),
            "variable": bool(is_var),
            "expressions": infer_expressions(note) if is_var else 0,
            "text": bool(h.get("is_text")),
            "jump": bool(h.get("is_jump")),
            "jump_operand": int(h.get("jump_operand_index", -1)),
            "confidence": h.get("confidence", "?"),
            "note": note[:400],
        }
        if is_var:
            variable.append((codes, spec))

        for code in codes:
            key = f"0x{code:04X}"
            if key in opcodes and opcodes[key] != spec:
                prev = opcodes[key]
                if (prev["operands"], prev["variable"], prev["text"], prev["jump"]) != (
                    spec["operands"], spec["variable"], spec["text"], spec["jump"]
                ):
                    conflicts.append((key, prev, spec))
                    continue
            opcodes[key] = spec

    print()
    print("=" * 72)
    print("MAPA CONSOLIDADO")
    print("=" * 72)
    print(f"  opcodes mapeados        : {len(opcodes)}")
    print(f"  de tamanho VARIAVEL     : {sum(1 for s in opcodes.values() if s['variable'])}")
    print(f"  de texto                : {sum(1 for s in opcodes.values() if s['text'])}")
    print(f"  de salto                : {sum(1 for s in opcodes.values() if s['jump'])}")
    print(f"  handlers sem opcode     : {len(unmapped)}")
    print(f"  conflitos               : {len(conflicts)}")
    for key, a, b in conflicts[:8]:
        print(f"      {key}: {a['addr']} vs {b['addr']}")

    var_sem_contagem = [
        k for k, s in opcodes.items() if s["variable"] and not s["expressions"] and not s["text"]
    ]
    print(f"  variaveis sem contagem de expressao: {len(var_sem_contagem)}")
    if var_sem_contagem:
        print(f"      {', '.join(sorted(var_sem_contagem)[:20])}")

    OPCODES_PATH.write_text(
        json.dumps(dict(sorted(opcodes.items())), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print()
    print(f"  gravado: {OPCODES_PATH}")

    # Os opcodes de salto sao os mais criticos - lista completa.
    print()
    print("=" * 72)
    print("OPCODES DE SALTO (os que exigem reflow)")
    print("=" * 72)
    for key, spec in sorted(opcodes.items()):
        if spec["jump"]:
            print(
                f"  {key}  operandos={spec['operands']} var={spec['variable']} "
                f"alvo=op[{spec['jump_operand']}]  conf={spec['confidence']}  {spec['addr']}"
            )

    print()
    print("=" * 72)
    print("OPCODES DE TEXTO")
    print("=" * 72)
    for key, spec in sorted(opcodes.items()):
        if spec["text"]:
            print(
                f"  {key}  expressoes={spec['expressions']} operandos={spec['operands']} "
                f"conf={spec['confidence']}  {spec['addr']}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
