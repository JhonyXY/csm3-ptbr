#!/usr/bin/env python3
"""Converte traducao.json para o formato que inject.py espera.

O tradutor grava uma entrada por TEXTO DISTINTO, com a lista de todas as
ocorrencias em `aplica_em`. O injetor quer uma entrada por OCORRENCIA, com
script e offset separados.

Serve tambem para injetar uma traducao PARCIAL: o que ainda nao foi traduzido
simplesmente nao entra, e o injetor mantem o japones nesses lugares.

    python3 preparar_injecao.py            # usa traducao.json
    python3 preparar_injecao.py outro.json
"""

from __future__ import annotations

import json
import shutil
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import encoder
from export_json import from_translatable

OUT = Path(__file__).parent / "_out"

# Uma fala e feita de VARIOS BLOCOS, um por linha de tela. O extrator junta os
# blocos num texto so para traduzir; aqui o portugues volta a ser distribuido
# entre eles. Sem isso o texto inteiro cai no primeiro bloco, passa da caixa e
# o jogo trava.
#
# Orcamento por linha: o bloco japones mais largo tem 18 caracteres de 12px.
LARGURA_LINHA_PX = 216

# NAO decodifique o id para achar script e offset.
#
# O formato e f<script em DECIMAL>_<offset em HEX> - misto, o que nao e obvio.
# Lendo os dois como hex, so casam os scripts 0 a 9, onde as duas leituras
# coincidem: 24 de 4.189 ocorrencias, e a injecao sai silenciosamente vazia.
# falas_originais.json ja traz os dois como campos; use-os.

# O modelo produz caracteres tipograficos que a fonte do jogo nao tem. Trocar
# aqui e melhor que a injecao morrer no meio: cada um destes foi visto de
# verdade nas traducoes (ver_chars_invalidos.py levanta a lista atual).
SUBSTITUICOES = {
    "º": "o",   "ª": "a",       # "4o premio" no lugar do ordinal
    "~": "",                    # o modelo usa para alongar vogal: "Mii~"
    "—": "-",   "–": "-",
    "“": '"',   "”": '"',   "„": '"',
    "‘": "'",   "’": "'",
    "«": '"',   "»": '"',
    "…": "...",
    " ": " ",              # espaco duro
    "​": "",               # espaco de largura zero
}


def normalizar(texto: str, contador: Counter) -> str:
    """Deixa o texto codificavel pela fonte do jogo.

    Tres niveis, do menos ao mais destrutivo: substituicao conhecida, remocao
    do acento, e por fim descarte do caractere. Tudo que muda e contado, para
    aparecer no relatorio em vez de sumir calado.
    """
    for de, para in SUBSTITUICOES.items():
        if de in texto:
            contador[f"{de!r} -> {para!r}"] += texto.count(de)
            texto = texto.replace(de, para)

    # As tags de nome ({g}, {d}, ...) viram os caracteres gregos AGORA, antes da
    # conferencia. Validar caractere a caractere com a tag inteira faria '{'
    # sozinho parecer invalido, e descarta-lo destruiria o marcador do nome do
    # personagem - foi o que aconteceu na primeira versao deste script.
    texto = from_translatable(texto)

    saida = []
    for ch in texto:
        try:
            encoder.encode(ch)
            saida.append(ch)
            continue
        except Exception:
            pass
        # Tenta sem o acento: 'ñ' vira 'n'.
        sem = "".join(c for c in unicodedata.normalize("NFD", ch)
                      if not unicodedata.combining(c))
        try:
            encoder.encode(sem)
            contador[f"{ch!r} -> {sem!r} (acento removido)"] += 1
            saida.append(sem)
        except Exception:
            contador[f"{ch!r} DESCARTADO"] += 1
    return "".join(saida)


def carregar_larguras():
    """char -> avanco em pixels, pela mesma tabela que o jogo usa."""
    import csm3rom
    import font as fontmod

    repo = Path(__file__).resolve().parents[2]
    rom = csm3rom.load_rom(repo / "baserom.gba")
    tabela = (OUT / "larguras.bin").read_bytes()
    largura = {}

    def por_codigo(ch, code):
        idx = fontmod.sjis_to_glyph_index(rom, code)
        if idx is not None and idx < len(tabela):
            largura[ch] = tabela[idx]

    for i in range(26):
        por_codigo(chr(ord("A") + i), 0x8260 + i)
        por_codigo(chr(ord("a") + i), 0x8281 + i)
    for i in range(10):
        por_codigo(chr(ord("0") + i), 0x824F + i)
    for ch, code in ((" ", 0x8140), ("?", 0x8148), ("!", 0x8149),
                     (",", 0x8143), (".", 0x8144), ("-", 0x815D),
                     (":", 0x8146), (";", 0x8147), ("'", 0x8166),
                     ('"', 0x8168), ("(", 0x8169), (")", 0x816A)):
        por_codigo(ch, code)
    mapa = json.loads((OUT / "acentos_mapa.json").read_text(encoding="utf-8"))
    for ch, hexcode in mapa.items():
        por_codigo(ch, int(hexcode, 16))
    return largura


def quebrar(texto: str, largura: dict):
    """Quebra o texto em linhas que cabem na caixa, SEM limite de quantidade.

    Nao cortar e o ponto: se o portugues precisa de 4 linhas onde o japones
    usava 3, o injetor cria a quarta duplicando a instrucao de texto. Espremer
    a traducao para caber no numero original de linhas seria perder conteudo a
    toa, tendo espaco disponivel.
    """
    media = sum(largura.values()) / len(largura)

    def px(s):
        return sum(largura.get(c, media) for c in s)

    linhas = []
    atual = ""
    for palavra in texto.split():
        tentativa = (atual + " " + palavra).strip()
        if atual and px(tentativa) > LARGURA_LINHA_PX:
            linhas.append(atual)
            atual = palavra
        else:
            atual = tentativa
    if atual:
        linhas.append(atual)
    return linhas or [""]


def distribuir(linhas: list[str], n_blocos: int, contador: Counter):
    """Reparte as linhas pelos blocos da fala.

    Cada bloco leva uma linha. Se sobrarem linhas, TODAS as que sobram vao no
    ultimo bloco, como lista - o injetor transforma cada uma numa instrucao
    nova logo depois dele, que e onde elas aparecem na tela.
    """
    if len(linhas) > n_blocos:
        contador[f"+{len(linhas) - n_blocos} linha(s) inserida(s)"] += 1
    saida = []
    for i in range(n_blocos):
        if i < n_blocos - 1:
            saida.append([linhas[i]] if i < len(linhas) else [""])
        else:
            saida.append(linhas[i:] if i < len(linhas) else [""])
    return saida


def main() -> int:
    nome = "traducao.json"
    max_scripts = None
    escolhidos = None
    for arg in sys.argv[1:]:
        if arg.startswith("--max-scripts="):
            max_scripts = int(arg.split("=", 1)[1])
        elif arg.startswith("--scripts="):
            escolhidos = {int(s) for s in arg.split("=", 1)[1].split(",")
                          if s.strip()}
        else:
            nome = arg
    origem = OUT / nome

    if not origem.exists():
        print(f"  nao existe: {origem}")
        return 1

    # O tradutor pode estar escrevendo agora. Copia antes de ler, para nao
    # pegar o arquivo pela metade.
    instantaneo = OUT / "traducao_instantaneo.json"
    shutil.copy2(origem, instantaneo)

    try:
        dados = json.loads(instantaneo.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"  JSON incompleto (o tradutor estava gravando): {exc}")
        print("  tente de novo em alguns segundos")
        return 1

    # Indice id -> (script, offset), direto de quem extraiu.
    originais = json.loads(
        (OUT / "falas_originais.json").read_text(encoding="utf-8"))
    # Guarda TODOS os blocos da fala, nao so o primeiro: cada bloco e uma linha
    # de tela e precisa receber o seu pedaco do portugues.
    onde = {}
    for grupo in ("falas", "itens"):
        for f in originais.get(grupo, []):
            if f.get("script") is None:
                continue
            blocos = [b["offset"] for b in f.get("estrutura") or []]
            if not blocos and f.get("offset") is not None:
                blocos = [f["offset"]]
            if blocos:
                onde[f["id"]] = (f["script"], blocos)

    largura = carregar_larguras()

    strings = []
    sem_id = 0
    falas_ok = 0
    trocas = Counter()
    for e in dados.get("traducoes", []):
        pt = (e.get("pt") or "").strip()
        if not pt or e.get("erro"):
            continue
        pt = normalizar(pt, trocas)
        if not pt:
            continue
        falas_ok += 1
        # aplica_em traz todas as copias da mesma fala; se faltar, usa o id.
        for ident in e.get("aplica_em") or [e.get("id")]:
            local = onde.get(ident)
            if local is None:
                sem_id += 1
                continue
            script, blocos = local
            reparte = distribuir(quebrar(pt, largura), len(blocos), trocas)
            for offset, linhas_do_bloco in zip(blocos, reparte):
                strings.append({
                    "script": script,
                    "offset": offset,
                    "pt": linhas_do_bloco,
                    "jp": e.get("jp", ""),
                })

    # A area livre da ROM tem 282 KB e o cartucho ja esta no teto de 32 MB do
    # GBA, entao nao da para crescer o arquivo. Traduzir tudo de uma vez nao
    # cabe: o texto e u16 por caractere e o portugues tem ~1,7x os caracteres
    # do japones. --max-scripts injeta so os primeiros scripts, que sao os do
    # comeco do jogo, para dar uma ROM testavel enquanto isso nao se resolve.
    if escolhidos is not None:
        antes = len(strings)
        strings = [s for s in strings if s["script"] in escolhidos]
        print(f"  SO os scripts {sorted(escolhidos)}: "
              f"{len(strings):,} de {antes:,} ocorrencias")

    if max_scripts is not None:
        primeiros = sorted({s["script"] for s in strings})[:max_scripts]
        permitidos = set(primeiros)
        antes = len(strings)
        strings = [s for s in strings if s["script"] in permitidos]
        print(f"  LIMITADO a {max_scripts} scripts: "
              f"{len(strings):,} de {antes:,} ocorrencias")

    destino = OUT / "para_injetar.json"
    destino.write_text(json.dumps({"strings": strings}, ensure_ascii=False,
                                  indent=1), encoding="utf-8")
    instantaneo.unlink()

    scripts = sorted({s["script"] for s in strings})
    print("=" * 72)
    print("PREPARO DA INJECAO")
    print("=" * 72)
    print(f"  falas distintas traduzidas : {falas_ok:,}")
    print(f"  ocorrencias a substituir   : {len(strings):,}")
    print(f"  scripts afetados           : {len(scripts)}")
    if sem_id:
        print(f"  ids fora do padrao (ignorados): {sem_id}")
    if trocas:
        print("\n  caracteres normalizados (a fonte nao os tem):")
        for troca, n in trocas.most_common():
            print(f"      {n:5d}x  {troca}")
    print(f"\n  gerado: _out/{destino.name}")
    print(f"\n  agora: python3 inject.py --traducao {destino.name} "
          f"--saida csm3_ptbr.gba")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
