"""Converte texto latino para as palavras Shift-JIS que o jogo ja sabe desenhar.

O jogo nao tem fonte de 1 byte, mas a fonte embutida JA CONTEM o alfabeto latino
de largura total (zenkaku): A-Z em SJIS 0x8260+, a-z em 0x8281+, digitos em
0x824F+. Usando essas faixas da para injetar portugues SEM tocar na engine - o
texto sai largo (12px por caractere) mas renderiza.

O empacotamento de 2 caracteres por palavra e o VWF vem depois; esta camada
existe para validar o injetor isoladamente.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from script_text import sjis_to_word

# Pontuacao e simbolos de largura total presentes na fonte.
PUNCT_SJIS = {
    " ": 0x8140,
    "　": 0x8140,
    ",": 0x8143,
    ".": 0x8144,
    ":": 0x8146,
    ";": 0x8147,
    "?": 0x8148,
    "!": 0x8149,
    "'": 0x8166,
    '"': 0x8168,
    "(": 0x8169,
    ")": 0x816A,
    "[": 0x816D,
    "]": 0x816E,
    "+": 0x817B,
    "-": 0x817C,
    "/": 0x815E,
    "=": 0x8181,
    "<": 0x8183,
    ">": 0x8184,
    "*": 0x8196,
    "@": 0x8197,
    "#": 0x8194,
    "%": 0x8193,
    "&": 0x8195,
}


class EncodeError(ValueError):
    pass


def strip_accents(text: str) -> str:
    """Remove acentos: a fonte original nao tem a/e/i/o/u acentuados.

    Quando o alfabeto latino proprio for desenhado nos 846 glifos livres, esta
    funcao sai de cena.
    """
    decomposed = unicodedata.normalize("NFD", text)
    out = []
    for ch in decomposed:
        if unicodedata.combining(ch):
            continue
        out.append(ch)
    result = "".join(out)
    # A cedilha some no NFD; o c fica. Casos que o NFD nao cobre:
    return result.replace("ç", "c").replace("Ç", "C")


def _carregar_acentos() -> dict[str, int]:
    """Mapa das acentuadas adicionadas a fonte por patch_acentos.py.

    Vazio se o patch nao tiver sido aplicado - ai encode() cai no
    strip_accents() e "acao" sai sem cedilha, como antes.
    """
    caminho = Path(__file__).parent / "_out" / "acentos_mapa.json"
    if not caminho.exists():
        return {}
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return {ch: int(code, 16) for ch, code in dados.items()}


ACENTOS_SJIS = _carregar_acentos()


def char_to_sjis(ch: str) -> int | None:
    """Devolve o codigo Shift-JIS (big-endian) do caractere, ou None."""
    if "A" <= ch <= "Z":
        return 0x8260 + (ord(ch) - ord("A"))
    if "a" <= ch <= "z":
        return 0x8281 + (ord(ch) - ord("a"))
    if "0" <= ch <= "9":
        return 0x824F + (ord(ch) - ord("0"))
    acentuada = ACENTOS_SJIS.get(ch)
    if acentuada is not None:
        return acentuada
    return PUNCT_SJIS.get(ch)


def encode(text: str, *, allow_japanese: bool = True) -> list[int]:
    """Codifica uma string em palavras u16 prontas para o stream de script.

    Caracteres japoneses passam direto (util para strings parcialmente
    traduzidas e para os placeholders de nome, que sao letras gregas).
    """
    words: list[int] = []
    for ch in text:
        code = char_to_sjis(ch)
        if code is not None:
            words.append(sjis_to_word(bytes((code >> 8, code & 0xFF))))
            continue

        # Nao e latino conhecido: tenta como Shift-JIS direto.
        try:
            raw = ch.encode("shift_jis")
        except UnicodeEncodeError:
            folded = strip_accents(ch)
            if folded != ch:
                words.extend(encode(folded, allow_japanese=allow_japanese))
                continue
            raise EncodeError(f"caractere sem representacao: {ch!r} (U+{ord(ch):04X})")

        if len(raw) == 1:
            # Meia largura: converte para a versao de largura total se possivel.
            raise EncodeError(f"caractere de 1 byte sem equivalente: {ch!r}")
        if len(raw) != 2:
            raise EncodeError(f"caractere ocupa {len(raw)} bytes: {ch!r}")
        if not allow_japanese:
            raise EncodeError(f"japones nao permitido aqui: {ch!r}")
        words.append(sjis_to_word(raw))

    return words


def decode(words: list[int]) -> str:
    from script_text import word_to_sjis

    raw = bytearray()
    for w in words:
        raw += word_to_sjis(w)
    return bytes(raw).decode("shift_jis")
