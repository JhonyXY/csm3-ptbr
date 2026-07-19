"""Especificacao estrutural dos opcodes.

Cada opcode e descrito por uma SEQUENCIA ordenada de elementos que ele consome
do stream, depois da propria palavra de opcode:

    "word"   uma palavra u16 inline (operando fixo)
    "expr"   uma expressao RPN, auto-delimitada (ver skip_expression)
    "string" uma string u16 terminada em 0x0000

Os opcodes criticos abaixo foram transcritos das notas da analise dos handlers,
que sao mais confiaveis que o campo numerico (varios handlers tem "0 operandos
fixos + 1 expressao", que o numero sozinho nao expressa).

`jump_from` indica de qual elemento sai o alvo do salto, no formato "word<N>"
onde N e o indice do elemento "word" na sequencia (0-based). None = o alvo nao
vem do stream (vem de pilha ou de variavel global), logo nao precisa realocacao.
"""

from __future__ import annotations

# Tokens da linguagem de expressao avaliada por sub_08012578.
# O loop le uma palavra; se for 0, encerra. Os tokens abaixo leem UMA palavra
# extra (o literal/indice); todos os outros consomem so a propria palavra.
EXPR_TOKENS_WITH_ARG = {0x0001, 0x0002, 0x0003}
EXPR_TERMINATOR = 0x0000

# Opcodes transcritos manualmente das notas da analise. Estes tem prioridade
# sobre o mapa automatico.
CRITICAL: dict[int, dict] = {
    # --- fluxo de controle (tabela hi=0x00) ---
    0x0001: {"seq": ["word", "word", "expr"], "jump_from": None,
             "note": "le 2 operandos inline (IP += 4) e depois avalia expressao"},
    0x0002: {"seq": ["word", "expr"], "jump_from": "word0",
             "note": "salto condicional: alvo lido ANTES da expressao"},
    0x0003: {"seq": ["word"], "jump_from": "word0",
             "note": "salto incondicional"},
    0x0005: {"seq": ["expr"], "jump_from": None,
             "note": "troca de blob de script; alvo nao vem do stream"},
    0x0006: {"seq": ["expr"], "jump_from": None,
             "note": "gosub entre blobs; empilha contexto"},
    0x0007: {"seq": ["word"], "jump_from": "word0",
             "note": "gosub dentro do mesmo blob"},
    0x0008: {"seq": [], "jump_from": None,
             "note": "retorno de gosub; alvo vem da pilha"},
    0x0009: {"seq": ["expr", "word"], "jump_from": "word0",
             "note": "spawn de thread: expressao = indice, palavra = entrada"},

    # --- texto (tabela hi=0x03) ---
    0x0307: {"seq": ["expr", "string"], "jump_from": None,
             "note": "copia string para buffer de nome"},
    0x0308: {"seq": ["string"], "jump_from": None,
             "note": "linha de mensagem - o caso dominante"},
    0x030B: {"seq": ["expr"] * 5 + ["string"], "jump_from": None,
             "note": "janela com 5 parametros + texto"},
    0x030D: {"seq": ["word", "string"], "jump_from": "word0",
             "note": "opcao de menu de escolha - o operando E offset de salto"},
    0x0311: {"seq": ["string"], "jump_from": None},
    0x0314: {"seq": ["word", "string"], "jump_from": "word0",
             "note": "opcao de menu (variante) - operando E offset de salto"},
    0x0316: {"seq": ["expr", "string"], "jump_from": None},
    0x0317: {"seq": ["string"], "jump_from": None},
    0x0363: {"seq": ["string"], "jump_from": None,
             "note": "copia string para o saveblock"},

    # --- saltos sem operando no stream ---
    0x030E: {"seq": [], "jump_from": None,
             "note": "alvo vem de global, nao do stream"},
    0x0315: {"seq": [], "jump_from": None,
             "note": "alvo vem de gUnk_03005560"},

    # --- achado da varredura de completude ---
    0x0202: {"seq": ["word"], "jump_from": "word0",
             "note": "spawn de corrotina via sub_08012D64; o operando E offset de codigo "
                     "e precisa de relocacao, mesmo o fluxo atual seguindo sequencial"},

    # --- corrigidos a partir das notas, apos o diagnostico de drift ---
    # Nestes o campo numerico da analise contava expressoes, nao palavras.
    0x0440: {"seq": ["expr"] * 4, "jump_from": None,
             "note": "4 chamadas a sub_08012578 = 4 expressoes RPN"},
    0x0460: {"seq": ["expr", "word", "expr"], "jump_from": None,
             "note": "caso misto: expressao, palavra crua, expressao"},
    0x0453: {"seq": ["expr", "word", "expr"], "jump_from": None,
             "note": "mesmo layout de 0x0460; a palavra crua tem cara de rotulo - "
                     "investigar quem le gUnk+0xA antes de tratar como numero comum"},
    0x040C: {"seq": ["expr", "word"], "jump_from": None,
             "note": "1 expressao, depois 1 palavra crua"},
    0x0461: {"seq": ["expr"], "jump_from": None},
    0x0361: {"seq": ["expr"], "jump_from": None},
    0x0360: {"seq": ["expr"], "jump_from": None},
    0x038C: {"seq": ["expr"], "jump_from": None},
}

STRING_TERMINATOR = 0x0000


import json as _json
from pathlib import Path as _Path

_SEQUENCES_PATH = _Path(__file__).parent / "_out" / "sequences.json"
_sequences: dict[int, dict] | None = None


def load_sequences() -> dict[int, dict]:
    """Carrega _out/sequences.json - a fonte autoritativa.

    Vem da analise que extraiu a SEQUENCIA ORDENADA de cada handler, em vez de
    uma contagem numerica (que nao distinguia palavra de expressao).
    """
    global _sequences
    if _sequences is None:
        if _SEQUENCES_PATH.exists():
            raw = _json.loads(_SEQUENCES_PATH.read_text(encoding="utf-8"))
            _sequences = {int(k, 16): v for k, v in raw.items()}
        else:
            _sequences = {}
    return _sequences


def spec_for(opcode: int, auto_map: dict[int, dict] | None = None) -> dict | None:
    """Devolve a especificacao de um opcode.

    Ordem de precedencia: sequences.json (analise ordenada) -> CRITICAL
    (correcoes manuais) -> None.
    """
    seqs = load_sequences()
    entry = seqs.get(opcode)
    if entry is not None:
        return {
            "seq": list(entry.get("seq", [])),
            "jump_from": entry.get("jump_from"),
            "note": f"{entry.get('addr','')} conf={entry.get('confidence','?')}",
        }

    if opcode in CRITICAL:
        return CRITICAL[opcode]

    return None
