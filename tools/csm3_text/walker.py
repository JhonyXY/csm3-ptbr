"""Percorre o bytecode instrucao a instrucao, respeitando a estrutura real de
cada opcode (operandos fixos, expressoes RPN e strings).

A varredura linear ingenua nao funciona porque:
  - o mesmo valor pode ser opcode ou token de expressao, dependendo do contexto;
  - muitos opcodes consomem expressoes RPN de tamanho variavel.

O walker so interpreta uma palavra como opcode quando ela esta numa fronteira de
instrucao de verdade.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from pathlib import Path

import opcode_spec
from opcode_spec import EXPR_TERMINATOR, EXPR_TOKENS_WITH_ARG, STRING_TERMINATOR

OPCODE_MAP_PATH = Path(__file__).parent / "_out" / "opcodes.json"
MAX_TABLE_HI = 0x04


def load_auto_map() -> dict[int, dict]:
    if not OPCODE_MAP_PATH.exists():
        return {}
    raw = json.loads(OPCODE_MAP_PATH.read_text(encoding="utf-8"))
    return {int(k, 16): v for k, v in raw.items()}


def skip_expression(body: bytes, pos: int, limit: int) -> tuple[int, list[int]]:
    """Consome uma expressao RPN, devolvendo a nova posicao e as palavras lidas.

    Reproduz sub_08012578: le uma palavra por iteracao; termina quando a palavra
    for 0. Os tokens 0x0001/0x0002/0x0003 leem uma palavra extra.
    """
    words: list[int] = []
    while pos + 2 <= limit:
        token = struct.unpack_from("<H", body, pos)[0]
        pos += 2
        words.append(token)
        if token == EXPR_TERMINATOR:
            return pos, words
        if token in EXPR_TOKENS_WITH_ARG:
            if pos + 2 > limit:
                break
            words.append(struct.unpack_from("<H", body, pos)[0])
            pos += 2
    return pos, words


def skip_string(body: bytes, pos: int, limit: int) -> tuple[int, list[int]]:
    """Consome uma string u16 terminada em 0x0000 (sem incluir o terminador)."""
    words: list[int] = []
    while pos + 2 <= limit:
        w = struct.unpack_from("<H", body, pos)[0]
        pos += 2
        if w == STRING_TERMINATOR:
            return pos, words
        words.append(w)
    return pos, words


@dataclass
class Instruction:
    offset: int
    opcode: int
    parts: list[tuple[str, list[int]]] = field(default_factory=list)
    size: int = 0
    known: bool = True

    @property
    def words(self) -> list[int]:
        """Operandos fixos, na ordem em que aparecem."""
        return [w[0] for kind, w in self.parts if kind == "word"]

    @property
    def text_words(self) -> list[int] | None:
        for kind, w in self.parts:
            if kind == "string":
                return w
        return None

    @property
    def is_text(self) -> bool:
        return self.text_words is not None


@dataclass
class WalkResult:
    instructions: list[Instruction]
    unknown_opcodes: dict[int, int]
    boundaries: set[int]
    jump_targets: set[int]
    errors: list[str]

    @property
    def text_instructions(self) -> list[Instruction]:
        return [i for i in self.instructions if i.is_text]

    @property
    def bad_jumps(self) -> set[int]:
        return {t for t in self.jump_targets if t not in self.boundaries}


def walk(body: bytes, auto_map: dict[int, dict] | None = None) -> WalkResult:
    n = len(body) & ~1
    pos = 0
    instructions: list[Instruction] = []
    unknown: dict[int, int] = {}
    boundaries: set[int] = set()
    jump_targets: set[int] = set()
    errors: list[str] = []

    while pos + 2 <= n:
        boundaries.add(pos)
        start = pos
        opcode = struct.unpack_from("<H", body, pos)[0]
        pos += 2

        spec = opcode_spec.spec_for(opcode, auto_map)
        known = spec is not None
        if not known:
            unknown[opcode] = unknown.get(opcode, 0) + 1
            if (opcode >> 8) > MAX_TABLE_HI:
                errors.append(f"@0x{start:04X}: 0x{opcode:04X} fora das tabelas")
            spec = {"seq": [], "jump_from": None}

        parts: list[tuple[str, list[int]]] = []
        for element in spec["seq"]:
            if element == "word":
                if pos + 2 > n:
                    errors.append(f"@0x{start:04X}: operando truncado")
                    break
                parts.append(("word", [struct.unpack_from("<H", body, pos)[0]]))
                pos += 2
            elif element == "expr":
                pos, words = skip_expression(body, pos, n)
                parts.append(("expr", words))
            elif element == "string":
                before = pos
                pos, words = skip_string(body, pos, n)
                if pos == before:
                    errors.append(f"@0x{start:04X}: string vazia sem terminador")
                parts.append(("string", words))

        jump_from = spec.get("jump_from")
        if jump_from and jump_from.startswith("word"):
            idx = int(jump_from[4:])
            fixed = [w[0] for kind, w in parts if kind == "word"]
            if idx < len(fixed):
                jump_targets.add(fixed[idx] & ~1)

        instructions.append(
            Instruction(
                offset=start,
                opcode=opcode,
                parts=parts,
                size=pos - start,
                known=known,
            )
        )

    return WalkResult(
        instructions=instructions,
        unknown_opcodes=unknown,
        boundaries=boundaries,
        jump_targets=jump_targets,
        errors=errors,
    )


def serialize(instructions: list[Instruction]) -> bytes:
    """Reconstroi o bytecode a partir da representacao estruturada."""
    out = bytearray()
    for ins in instructions:
        out += struct.pack("<H", ins.opcode)
        for kind, words in ins.parts:
            for w in words:
                out += struct.pack("<H", w)
            if kind == "string":
                out += struct.pack("<H", STRING_TERMINATOR)
    return bytes(out)
