"""Localizacao e decodificacao das strings dentro do bytecode de script.

O texto nao fica em uma area separada: ele esta embutido no proprio stream de
bytecode. Um opcode marcador e seguido diretamente pelas palavras da string, que
termina na palavra 0x0000.

Cada palavra de texto e um par Shift-JIS lido como u16 little-endian, ou seja, o
BYTE BAIXO da palavra e o lead byte do Shift-JIS.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

# Opcodes que iniciam uma string, e quantas palavras de operando vem ANTES do
# texto comecar. Derivado da analise dos handlers e validado estatisticamente.
TEXT_MARKERS = {
    0x0308: 0,  # exibir linha de mensagem (95,6% dos casos)
    0x0363: 0,  # variante de mensagem
    0x0314: 1,  # item de menu: 1 operando (offset) antes do texto
}

TERMINATOR = 0x0000

# Lead bytes validos de Shift-JIS de 2 bytes.
SJIS_LEAD_RANGES = ((0x81, 0x9F), (0xE0, 0xEF))
SJIS_TRAIL_RANGES = ((0x40, 0x7E), (0x80, 0xFC))


def is_sjis_pair(word: int) -> bool:
    lead = word & 0xFF
    trail = word >> 8
    if not any(lo <= lead <= hi for lo, hi in SJIS_LEAD_RANGES):
        return False
    return any(lo <= trail <= hi for lo, hi in SJIS_TRAIL_RANGES)


def word_to_sjis(word: int) -> bytes:
    """Converte a palavra u16 para o par de bytes Shift-JIS na ordem natural."""
    return bytes((word & 0xFF, word >> 8))


def sjis_to_word(pair: bytes) -> int:
    if len(pair) != 2:
        raise ValueError(f"esperado 2 bytes, recebido {len(pair)}")
    return pair[0] | (pair[1] << 8)


@dataclass
class TextRun:
    """Uma string localizada dentro de um blob de script."""

    script: int
    marker: int  # o opcode que iniciou a string
    marker_offset: int  # offset do opcode dentro do body
    text_offset: int  # offset da primeira palavra de texto
    words: list[int] = field(default_factory=list)
    operands: list[int] = field(default_factory=list)

    @property
    def end_offset(self) -> int:
        """Offset logo apos a palavra terminadora."""
        return self.text_offset + len(self.words) * 2 + 2

    @property
    def raw(self) -> bytes:
        out = bytearray()
        for w in self.words:
            out += word_to_sjis(w)
        return bytes(out)

    def decode(self, errors: str = "strict") -> str:
        return self.raw.decode("shift_jis", errors=errors)


def scan_text_runs(body: bytes, script_index: int = -1) -> list[TextRun]:
    """Varre o bytecode procurando strings.

    A varredura e linear em passos de 2 bytes. Nao tenta interpretar o fluxo de
    controle: procura os opcodes marcadores e, ao achar um, le ate o terminador.
    Como o texto e sempre precedido por um marcador conhecido e sempre terminado
    por 0x0000, isso e suficiente para localizar as strings sem conhecer o
    tamanho de operando de todos os opcodes.
    """
    runs: list[TextRun] = []
    n = len(body) & ~1
    pos = 0

    while pos < n:
        word = struct.unpack_from("<H", body, pos)[0]
        pre_operands = TEXT_MARKERS.get(word)
        if pre_operands is None:
            pos += 2
            continue

        marker_offset = pos
        pos += 2

        operands = []
        for _ in range(pre_operands):
            if pos + 2 > n:
                break
            operands.append(struct.unpack_from("<H", body, pos)[0])
            pos += 2

        text_offset = pos
        words: list[int] = []
        while pos < n:
            w = struct.unpack_from("<H", body, pos)[0]
            pos += 2
            if w == TERMINATOR:
                break
            words.append(w)

        # Um marcador seguido imediatamente do terminador e uma string vazia;
        # mantemos para preservar a estrutura na reinjecao.
        runs.append(
            TextRun(
                script=script_index,
                marker=word,
                marker_offset=marker_offset,
                text_offset=text_offset,
                words=words,
                operands=operands,
            )
        )

    return runs


def classify_words(runs: list[TextRun]) -> dict[int, int]:
    """Frequencia de cada palavra distinta que aparece dentro de strings."""
    freq: dict[int, int] = {}
    for run in runs:
        for w in run.words:
            freq[w] = freq.get(w, 0) + 1
    return freq
