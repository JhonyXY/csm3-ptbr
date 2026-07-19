#!/usr/bin/env python3
"""Migra as strings de sistema para o build, via linker.

Estrategia: NAO mexer em nada que ja existe. Como 102.100 ponteiros crus dentro
dos .incbin quebrariam se os dados existentes deslocassem, as strings novas vao
para um arquivo NOVO adicionado ao FINAL da secao rom. Assim:

  - nada que existe muda de endereco
  - os 43 ponteiros viram .4byte simbolico
  - o linker resolve os enderecos finais sozinho

Gera/modifica:
  data/ptbr.s          arquivo novo com as strings traduzidas
  data/data1.s         os 43 .incbin de ponteiro viram .4byte <simbolo>
  linker.ld            acrescenta data/ptbr.o(.rodata) no fim da secao rom

O Makefile ja pega data/ptbr.s sozinho (usa wildcard em data/*.s).

    python3 migrar_para_build.py            # aplica
    python3 migrar_para_build.py --reverter # desfaz
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import encoder

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "_out"

PTBR_S = REPO / "data" / "ptbr.s"
DATA1 = REPO / "data" / "data1.s"
LINKER = REPO / "linker.ld"
MAKEFILE = REPO / "Makefile"

MARCA = "data/ptbr.o(.rodata);"
BACKUP_SUFIXO = ".pre-ptbr"


def rotulo(indice: int) -> str:
    return f"gPtBrSys_{indice:02d}"


def fazer_backup(path: Path) -> None:
    bkp = path.with_suffix(path.suffix + BACKUP_SUFIXO)
    if not bkp.exists():
        shutil.copy2(path, bkp)


def patch_makefile() -> bool:
    """Tira tools/csm3_text da lista de ferramentas a compilar.

    O Makefile trata todo tools/* como diretorio de ferramenta em C e roda
    make -C nele. As ferramentas deste projeto sao Python e nao tem Makefile.
    """
    fazer_backup(MAKEFILE)
    texto = MAKEFILE.read_text(encoding="utf-8")
    antigo = "TOOLDIRS := $(filter-out tools/agbcc tools/binutils,$(wildcard tools/*))"
    novo = ("TOOLDIRS := $(filter-out tools/agbcc tools/binutils tools/csm3_text,"
            "$(wildcard tools/*))")

    if novo in texto:
        print("  Makefile ja estava ajustado")
        return True
    if antigo not in texto:
        print("  ERRO: nao achei a linha TOOLDIRS no Makefile")
        return False

    MAKEFILE.write_text(texto.replace(antigo, novo, 1), encoding="utf-8")
    print("  Makefile: tools/csm3_text excluido do build de ferramentas")
    return True


def reverter() -> int:
    print("=" * 72)
    print("REVERTENDO")
    print("=" * 72)
    for path in (DATA1, LINKER, MAKEFILE):
        bkp = path.with_suffix(path.suffix + BACKUP_SUFIXO)
        if bkp.exists():
            shutil.copy2(bkp, path)
            bkp.unlink()
            print(f"  restaurado: {path.relative_to(REPO)}")
        else:
            print(f"  sem backup: {path.relative_to(REPO)}")
    if PTBR_S.exists():
        PTBR_S.unlink()
        print(f"  removido  : {PTBR_S.relative_to(REPO)}")
    return 0


def gerar_ptbr_s(entradas: list[dict]) -> int:
    linhas = [
        "\t.include \"asm/macros.inc\"",
        "\t.include \"constants/constants.inc\"",
        "",
        "\t.section .rodata",
        "",
        "@ Strings de sistema traduzidas para PT-BR.",
        "@ Gerado por tools/csm3_text/migrar_para_build.py - nao editar a mao.",
        "@ Codificacao: Shift-JIS de largura total (o alfabeto latino ja existe",
        "@ na fonte do jogo), como palavras u16 little-endian, terminadas em 0.",
        "",
    ]

    vistos: dict[str, str] = {}
    distintas = 0
    total_bytes = 0

    for e in entradas:
        pt = e["pt"]
        idx = e["indice"]
        if pt in vistos:
            # Reaproveita o rotulo de uma string identica ja emitida.
            continue
        nome = rotulo(idx)
        vistos[pt] = nome
        distintas += 1

        palavras = encoder.encode(pt)
        linhas.append(f"{nome}:: @ \"{pt}\"")
        for i in range(0, len(palavras), 8):
            bloco = palavras[i:i + 8]
            valores = ", ".join(f"0x{w:04X}" for w in bloco)
            linhas.append(f"\t.2byte {valores}")
        linhas.append("\t.2byte 0x0000")
        linhas.append("")
        total_bytes += len(palavras) * 2 + 2

    PTBR_S.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"  gerado: data/ptbr.s  ({distintas} strings, {total_bytes} bytes)")

    # Guarda o mapa texto -> rotulo para a substituicao dos ponteiros.
    return distintas, vistos


INCBIN_RE = re.compile(
    r'^\s*\.incbin\s+"baserom\.gba",\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+)'
)
LABEL_RE = re.compile(r"^(\w+)::")


def rotulo_referenciado(nome: str) -> bool:
    """O rotulo e usado em algum lugar do repo (fora da propria definicao)?"""
    for sub in ("asm", "src", "include", "data"):
        for path in (REPO / sub).rglob("*"):
            if not path.is_file() or path.suffix not in (".s", ".c", ".h", ".inc"):
                continue
            if path.name == "ptbr.s":
                continue
            for linha in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if nome in linha and not linha.startswith(f"{nome}::"):
                    return True
    return False


def patch_data1(entradas: list[dict], mapa: dict[str, str]) -> int:
    """Converte os .incbin dos ponteiros em .4byte simbolico.

    Alguns ponteiros compartilham um bloco .incbin maior, e um deles esta
    partido entre dois blocos. O algoritmo reescreve cada bloco afetado como uma
    sequencia de pedacos: .incbin para os bytes que continuam crus e .4byte para
    cada ponteiro.
    """
    fazer_backup(DATA1)
    linhas = DATA1.read_text(encoding="utf-8").splitlines()

    # Indexa os blocos com sua linha e rotulo.
    blocos = []
    label = None
    for i, linha in enumerate(linhas):
        m = LABEL_RE.match(linha)
        if m:
            label = m.group(1)
            continue
        m = INCBIN_RE.match(linha)
        if m:
            blocos.append({
                "linha": i, "rotulo": label,
                "off": int(m.group(1), 16), "size": int(m.group(2), 16),
            })

    por_ptr = {e["ponteiro"]: mapa[e["pt"]] for e in entradas}
    pendentes = set(por_ptr)

    # Para cada ponteiro, quais blocos ele toca. Um ponteiro de 4 bytes pode
    # atravessar a fronteira entre dois blocos (o caso de 0xBC9F10 + 0xBC9F11).
    afetados: dict[int, list[int]] = {}   # indice do bloco -> ponteiros
    toca: dict[int, list[int]] = {}       # ponteiro -> indices de bloco
    for ptr in sorted(por_ptr):
        for idx, b in enumerate(blocos):
            if b["off"] < ptr + 4 and ptr < b["off"] + b["size"]:
                afetados.setdefault(idx, []).append(ptr)
                toca.setdefault(ptr, []).append(idx)

    # Union-find: dois blocos so entram no mesmo grupo se ALGUM ponteiro toca os
    # dois. Blocos vizinhos que nao compartilham ponteiro ficam separados.
    pai: dict[int, int] = {idx: idx for idx in afetados}

    def raiz(x: int) -> int:
        while pai[x] != x:
            pai[x] = pai[pai[x]]
            x = pai[x]
        return x

    def unir(a: int, b: int) -> None:
        ra, rb = raiz(a), raiz(b)
        if ra != rb:
            pai[max(ra, rb)] = min(ra, rb)

    for ptr, idxs in toca.items():
        for outro in idxs[1:]:
            unir(idxs[0], outro)

    por_raiz: dict[int, list[int]] = {}
    for idx in afetados:
        por_raiz.setdefault(raiz(idx), []).append(idx)
    grupos = [sorted(v) for _, v in sorted(por_raiz.items())]

    removidos = []
    substituicoes: dict[int, list[str]] = {}   # linha original -> linhas novas
    apagar: set[int] = set()

    for grupo in grupos:
        primeiro, ultimo = blocos[grupo[0]], blocos[grupo[-1]]
        inicio = primeiro["off"]
        fim = ultimo["off"] + ultimo["size"]
        ptrs = sorted({p for i in grupo for p in afetados[i]})

        # Rotulos intermediarios do grupo serao perdidos - so pode se ninguem usa.
        for i in grupo[1:]:
            nome = blocos[i]["rotulo"]
            if nome and rotulo_referenciado(nome):
                print(f"  ERRO: {nome} e referenciado; nao posso remover o bloco")
                return -1
            if nome:
                removidos.append(nome)

        novas: list[str] = []
        cursor = inicio
        for ptr in ptrs:
            if ptr > cursor:
                novas.append(f'\t.incbin "baserom.gba", 0x{cursor:X}, 0x{ptr-cursor:X}')
            novas.append(f"\t.4byte {por_ptr[ptr]}")
            pendentes.discard(ptr)
            cursor = ptr + 4
        if fim > cursor:
            novas.append(f'\t.incbin "baserom.gba", 0x{cursor:X}, 0x{fim-cursor:X}')

        substituicoes[primeiro["linha"]] = novas
        for i in grupo[1:]:
            apagar.add(blocos[i]["linha"])
            if blocos[i]["rotulo"]:
                # apaga tambem a linha do rotulo e a linha em branco antes
                for j in range(blocos[i]["linha"] - 1, max(0, blocos[i]["linha"] - 3), -1):
                    if LABEL_RE.match(linhas[j]):
                        apagar.add(j)
                        break

    if pendentes:
        print(f"  ERRO: {len(pendentes)} ponteiros nao localizados: "
              + ", ".join(f"0x{p:07X}" for p in sorted(pendentes)))
        return -1

    saida = []
    for i, linha in enumerate(linhas):
        if i in apagar:
            continue
        if i in substituicoes:
            saida.extend(substituicoes[i])
        else:
            saida.append(linha)

    DATA1.write_text("\n".join(saida) + "\n", encoding="utf-8")
    print(f"  data/data1.s: {len(por_ptr)} ponteiros viraram .4byte simbolico")
    print(f"                {len(grupos)} blocos reescritos")
    if removidos:
        print(f"                rotulos absorvidos (nao referenciados): "
              f"{', '.join(removidos)}")
    return len(por_ptr)


def patch_linker() -> bool:
    fazer_backup(LINKER)
    texto = LINKER.read_text(encoding="utf-8")
    if MARCA in texto:
        print("  linker.ld ja continha a entrada")
        return True

    ancora = "        data/data1.o(.rodata);\n"
    if ancora not in texto:
        print("  ERRO: nao achei a ancora no linker.ld")
        return False

    texto = texto.replace(
        ancora,
        ancora + f"        {MARCA} /* strings PT-BR - sempre por ultimo */\n",
        1,
    )
    LINKER.write_text(texto, encoding="utf-8")
    print("  linker.ld: data/ptbr.o(.rodata) adicionado no fim da secao rom")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reverter", action="store_true")
    args = ap.parse_args()

    if args.reverter:
        return reverter()

    dados = json.loads((OUT / "sysstrings.json").read_text(encoding="utf-8"))
    entradas = [e for e in dados["strings"] if (e.get("pt") or "").strip()]

    print("=" * 72)
    print("MIGRACAO DAS STRINGS DE SISTEMA PARA O BUILD")
    print("=" * 72)
    print(f"  strings a migrar: {len(entradas)}")
    print()

    distintas, mapa = gerar_ptbr_s(entradas)
    if patch_data1(entradas, mapa) < 0:
        return 1
    if not patch_linker():
        return 1
    if not patch_makefile():
        return 1

    print()
    print("  Nada que ja existia mudou de endereco: as strings novas entram")
    print("  DEPOIS de data1.o, no fim da secao rom.")
    print()
    print("  Agora rode: DEVKITARM=/home/jhony/devkitARM make -j$(nproc)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
