#!/usr/bin/env python3
"""Fase 3: reinjeta o texto traduzido na ROM.

O trabalho perigoso e o REFLOW. Quando uma string muda de tamanho, tudo que vem
depois dela no blob se desloca - e os 13 opcodes que carregam offset de codigo
passam a apontar para o lugar errado. Este injetor:

  1. percorre o blob em instrucoes
  2. substitui as strings traduzidas
  3. monta o mapa offset_antigo -> offset_novo
  4. reescreve TODOS os operandos de offset de codigo usando o mapa
  5. re-serializa, atualiza o header PSI3, recomprime
  6. remonta a tabela do archive
  7. RE-VALIDA o resultado percorrendo o blob de novo

O passo 7 e o que impede um bug silencioso: se algum salto passar a cair fora de
fronteira depois da injecao, o processo aborta em vez de gerar uma ROM quebrada.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csm3rom
import encoder
import lz77
import walker
from export_json import from_translatable, IDEOGRAPHIC_SPACE

ROM_PATH = Path(__file__).resolve().parents[2] / "baserom.gba"
OUT_DIR = Path(__file__).parent / "_out"

# Fim dos dados da ROM original: dali ate 0x2000000 e padding zerado.
# Medido em csm3-freespace.sh: 275,5 KiB livres.
FREE_REGION_START = 0x1FBB1ED


class InjectError(RuntimeError):
    pass


class _FalsaIns:
    """Instrucao so com o que code_offset_words precisa.

    As instrucoes inseridas (linhas extras) nao vem do walker, entao nao ha
    objeto Instruction para elas. Como code_offset_words so olha opcode e parts,
    este par basta e evita depender da forma interna do walker.
    """

    __slots__ = ("opcode", "parts")

    def __init__(self, opcode, parts):
        self.opcode = opcode
        self.parts = parts


def code_offset_words(ins: walker.Instruction, spec: dict) -> list[int]:
    """Indices, dentro de ins.parts, dos elementos que carregam offset de codigo."""
    jf = spec.get("jump_from")
    if not jf or not jf.startswith("word"):
        return []
    target = int(jf[4:])
    seen = 0
    out = []
    for i, (kind, _) in enumerate(ins.parts):
        if kind == "word":
            if seen == target:
                out.append(i)
            seen += 1
    return out


def rebuild_script(script, translations: dict[int, str], auto_map) -> tuple[bytearray, dict]:
    """Reconstroi o corpo de um script com as traducoes aplicadas.

    `translations` mapeia offset_da_instrucao -> texto em portugues.
    """
    body = bytes(script.body)
    result = walker.walk(body, auto_map)
    stats = Counter()

    # --- passo 1: aplica as traducoes, INSERINDO linhas quando preciso --------
    #
    # Uma fala e uma sequencia de instrucoes de texto, uma por linha de tela. O
    # portugues costuma precisar de MAIS linhas que o japones (~1,7x os
    # caracteres para dizer o mesmo). Em vez de espremer a traducao ate caber,
    # duplica-se a instrucao de texto: cada linha extra vira uma instrucao nova,
    # clone da original, logo depois dela.
    #
    # Isso funciona porque o offset_map do passo 2 e reconstruido a partir dos
    # TAMANHOS NOVOS: instrucoes inseridas empurram as seguintes e todos os
    # saltos se ajustam sozinhos. So os offsets ORIGINAIS entram no mapa, que e
    # o que os saltos referenciam.
    #
    # `translations` aceita str (uma linha) ou list[str] (varias).
    plano: list[tuple[int, list, int | None]] = []   # (opcode, parts, offset)

    for ins in result.instructions:
        parts = [[kind, list(words)] for kind, words in ins.parts]

        if ins.offset in translations:
            pt = translations[ins.offset]
            linhas = [pt] if isinstance(pt, str) else list(pt)
            # Mantem a lista como veio: uma entrada vazia significa "apagar
            # este bloco", nao "deixar como estava".
            if not linhas:
                linhas = [""]

            def codificar(texto: str):
                try:
                    return encoder.encode(from_translatable(texto))
                except encoder.EncodeError as exc:
                    raise InjectError(
                        f"script {script.index} @0x{ins.offset:04X}: {exc}"
                    ) from exc

            for p in parts:
                if p[0] == "string":
                    p[1] = codificar(linhas[0])
                    stats["strings_traduzidas"] += 1
                    break

            plano.append((ins.opcode, parts, ins.offset))

            # As linhas que sobraram viram instrucoes novas, identicas a esta
            # menos o texto.
            for extra in linhas[1:]:
                clone = [[kind, list(words)] for kind, words in ins.parts]
                for p in clone:
                    if p[0] == "string":
                        p[1] = codificar(extra)
                        break
                plano.append((ins.opcode, clone, None))
                stats["linhas_inseridas"] += 1
            continue

        plano.append((ins.opcode, parts, ins.offset))

    new_sizes: list[int] = []
    new_parts: list[list] = []
    for opcode, parts, _ in plano:
        size = 2
        for kind, words in parts:
            size += len(words) * 2
            if kind == "string":
                size += 2  # terminador
        new_sizes.append(size)
        new_parts.append(parts)

    # --- passo 2: mapa de offsets (so os originais; os inseridos nao sao alvo)
    offset_map: dict[int, int] = {}
    pos = 0
    for (opcode, parts, offset), size in zip(plano, new_sizes):
        if offset is not None:
            offset_map[offset] = pos
        pos += size
    new_len = pos

    if new_len > 0xFFFE:
        raise InjectError(
            f"script {script.index}: corpo ficaria com {new_len} bytes, "
            f"acima do limite de 0xFFFE que o operando u16 de salto endereca"
        )

    # --- passo 3: reescreve os offsets de codigo
    for (opcode, parts, _), _sz in zip(plano, new_sizes):
        spec = walker.opcode_spec.spec_for(opcode, auto_map)
        if not spec:
            continue
        ins = _FalsaIns(opcode, parts)
        for idx in code_offset_words(ins, spec):
            old_target = parts[idx][1][0] & ~1
            if old_target not in offset_map:
                # Alvo que nao cai em fronteira nao deveria existir - o walker ja
                # provou que nao existe. Se aparecer, e bug e tem que estourar.
                raise InjectError(
                    f"script {script.index} @0x{ins.offset:04X}: alvo 0x{old_target:04X} "
                    f"nao corresponde a nenhuma instrucao"
                )
            new_target = offset_map[old_target]
            if new_target != old_target:
                stats["saltos_realocados"] += 1
            parts[idx][1][0] = new_target

    # --- passo 4: serializa
    out = bytearray()
    for opcode, parts, _ in plano:
        out += struct.pack("<H", opcode)
        for kind, words in parts:
            for w in words:
                out += struct.pack("<H", w)
            if kind == "string":
                out += struct.pack("<H", 0x0000)

    # Preserva o byte impar final, se houver.
    tail = body[len(walker.serialize(result.instructions)):]
    if tail:
        out += tail

    return out, stats


def verify_rebuilt(index: int, body: bytes, auto_map) -> None:
    """Re-valida o blob reconstruido. Aborta se algo ficou inconsistente."""
    result = walker.walk(body, auto_map)
    if result.unknown_opcodes:
        piores = ", ".join(f"0x{o:04X}" for o in list(result.unknown_opcodes)[:5])
        raise InjectError(f"script {index}: opcodes desconhecidos apos injecao: {piores}")
    if result.bad_jumps:
        alvos = ", ".join(f"0x{t:04X}" for t in sorted(result.bad_jumps)[:5])
        raise InjectError(f"script {index}: saltos fora de fronteira apos injecao: {alvos}")
    if result.errors:
        raise InjectError(f"script {index}: {result.errors[0]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--traducao", default="traducao_teste.json",
                    help="JSON com o campo pt preenchido")
    ap.add_argument("--saida", default="csm3_ptbr.gba")
    ap.add_argument("--rom", default="baserom.gba",
                    help="ROM de entrada. Para juntar o dialogo traduzido COM o "
                         "motor de VWF, aponte para csm3.gba (a saida do "
                         "build-ptbr.sh); do contrario o texto entra na ROM "
                         "japonesa crua e sai sem largura variavel nem acentos.")
    ap.add_argument("--dry-run", action="store_true",
                    help="valida sem escrever a ROM")
    args = ap.parse_args()

    trad_path = OUT_DIR / args.traducao
    if not trad_path.exists():
        print(f"ERRO: {trad_path} nao encontrado", file=sys.stderr)
        return 1

    payload = json.loads(trad_path.read_text(encoding="utf-8"))
    # `pt` pode ser uma string (uma linha) ou uma lista (a linha do bloco mais
    # as que sobraram, que viram instrucoes novas depois dele).
    por_script: dict[int, dict[int, list]] = {}
    for e in payload["strings"]:
        pt = e.get("pt") or ""
        linhas = [pt] if isinstance(pt, str) else list(pt)
        linhas = [l.strip() for l in linhas if isinstance(l, str) and l.strip()]
        # LISTA VAZIA NAO E "PULAR", E "APAGAR".
        #
        # Quando o portugues ocupa 2 linhas onde o japones usava 3, o terceiro
        # bloco fica sem texto. Pular esse bloco deixaria o japones original na
        # tela, no meio da fala traduzida. Grava string vazia para limpa-lo.
        if not linhas:
            linhas = [""]
        por_script.setdefault(e["script"], {})[e["offset"]] = linhas

    total_trad = sum(len(v) for v in por_script.values())
    print("=" * 72)
    print("INJECAO")
    print("=" * 72)
    print(f"  traducoes carregadas: {total_trad:,} em {len(por_script)} scripts")

    rom_entrada = Path(__file__).resolve().parents[2] / args.rom
    if not rom_entrada.exists():
        print(f"ERRO: {rom_entrada} nao encontrado", file=sys.stderr)
        return 1
    print(f"  ROM de entrada      : {rom_entrada.name}")
    rom = bytearray(csm3rom.load_rom(rom_entrada))
    auto_map = walker.load_auto_map()
    archive = csm3rom.open_archive(bytes(rom), csm3rom.SCRIPT_ARCHIVE)

    # Blobs NAO traduzidos mantem os bytes comprimidos originais: recomprimir
    # 1123 blobs intocados so para mudar 1 seria risco sem beneficio.
    comprimidos: dict[int, bytes] = {}
    stats = Counter()
    for entry in archive.entries:
        if entry.is_empty:
            continue

        translations = por_script.get(entry.index, {})
        if not translations:
            comprimidos[entry.index] = archive.raw(entry.index)
            stats["blobs_preservados"] += 1
            continue

        script = csm3rom.load_script(archive, entry.index)
        if script is None:
            continue
        new_body, s = rebuild_script(script, translations, auto_map)
        stats.update(s)
        verify_rebuilt(entry.index, bytes(new_body), auto_map)
        script.body = new_body
        comprimidos[entry.index] = lz77.compress(script.to_blob())
        stats["scripts_modificados"] += 1

    print(f"  scripts modificados : {stats['scripts_modificados']}")
    print(f"  blobs preservados   : {stats['blobs_preservados']} (bytes originais intactos)")
    print(f"  strings substituidas: {stats['strings_traduzidas']}")
    print(f"  linhas INSERIDAS    : {stats['linhas_inseridas']} "
          f"(o portugues precisou de mais linhas que o japones)")
    print(f"  saltos realocados   : {stats['saltos_realocados']}")
    print(f"  re-validacao        : OK (0 saltos invalidos, 0 opcodes desconhecidos)")

    # --- realoca so o que cresceu -----------------------------------------
    # O archive 2 esta empacotado sem folga: o archive 1 comeca logo depois.
    # Mas a entrada guarda o offset como u32 em unidades de 16 bytes, com
    # alcance de gigabytes - entao um blob pode morar em qualquer lugar da ROM.
    # Estrategia: blobs intocados ficam EXATAMENTE onde estao; os modificados vao
    # para o espaco livre no fim da ROM. Diff minimo, sem patch de codigo.
    print()
    print("=" * 72)
    print("REALOCACAO DOS BLOBS MODIFICADOS")
    print("=" * 72)

    base = csm3rom.ARCHIVE_OFFSETS[csm3rom.SCRIPT_ARCHIVE]
    # O offset da entrada e (posicao - base) / 16, e a base NAO e alinhada em 16
    # (0x1718FFC termina em C). Entao as posicoes validas sao as congruentes a
    # base modulo 16 - alinhar em 16 absoluto geraria um offset truncado.
    # ACHAR O FIM DO CONTEUDO, NAO CONFIAR NA CONSTANTE.
    #
    # FREE_REGION_START foi medido na baserom. Ao injetar na csm3.gba - que e o
    # que junta o dialogo traduzido ao motor de VWF - essa area deixou de estar
    # livre: o linker poe o codigo novo la (PtBrDesenhaGlifo em 0x09FC0CD8, ou
    # seja offset 0x1FC0CD8, quase 22 KB DEPOIS de 0x1FBB1ED). Gravar blobs a
    # partir da constante escrevia por cima do proprio desenhador de fonte, e o
    # jogo so quebrava na hora de desenhar texto - tela preta ao escolher o
    # personagem, enquanto a ROM sem injecao funcionava.
    #
    # Varre de tras para frente ate o ultimo byte com conteudo. Funciona
    # qualquer que seja o tamanho do codigo acrescentado, hoje e depois.
    fim_conteudo = len(rom)
    while fim_conteudo > 0 and rom[fim_conteudo - 1] == 0:
        fim_conteudo -= 1
    inicio_seguro = max(FREE_REGION_START, fim_conteudo)
    livre_ini = base + ((inicio_seguro - base + 15) // 16) * 16
    if fim_conteudo > FREE_REGION_START:
        print(f"  conteudo ate 0x{fim_conteudo:07X} "
              f"({fim_conteudo - FREE_REGION_START:,} bytes depois da constante)")
    livre_fim = len(rom)
    disponivel = livre_fim - livre_ini
    print(f"  regiao livre: 0x{livre_ini:07X}..0x{livre_fim:07X} "
          f"({disponivel:,} bytes)")
    assert (livre_ini - base) % 16 == 0, "inicio da regiao livre desalinhado"

    cursor = livre_ini
    realocados = 0
    novas_entradas: dict[int, tuple[int, int]] = {}

    for entry in archive.entries:
        if entry.is_empty:
            continue
        comp = comprimidos[entry.index]
        if entry.index not in por_script:
            continue  # intocado: mantem offset e tamanho originais

        padded = comp + b"\x00" * ((16 - len(comp) % 16) % 16)
        if cursor + len(padded) > livre_fim:
            print(f"\n  ERRO: espaco livre esgotado no script {entry.index}.")
            print(f"  Precisaria de mais {cursor + len(padded) - livre_fim:,} bytes.")
            return 1
        novas_entradas[entry.index] = ((cursor - base) // 16, len(padded) // 16)
        if not args.dry_run:
            rom[cursor : cursor + len(padded)] = padded
        cursor += len(padded)
        realocados += 1

    usado = cursor - livre_ini
    print(f"  blobs realocados : {realocados}")
    print(f"  espaco usado     : {usado:,} bytes ({100*usado/disponivel:.2f}% do livre)")
    print(f"  ainda disponivel : {disponivel - usado:,} bytes")

    # Reescreve so as entradas que mudaram.
    for index, (off, size) in novas_entradas.items():
        pos = base + 8 + index * 8
        if not args.dry_run:
            struct.pack_into("<II", rom, pos, off, size)

    print(f"  entradas alteradas na tabela: {len(novas_entradas)}")

    if args.dry_run:
        print("\n  --dry-run: nada foi escrito")
        return 0

    out_path = ROM_PATH.parent / args.saida
    out_path.write_bytes(bytes(rom))
    print()
    print(f"  ROM gravada: {out_path} ({len(rom):,} bytes)")

    # --- prova final: reabre a ROM gerada e valida tudo de novo -------------
    print()
    print("=" * 72)
    print("VALIDACAO DA ROM GERADA")
    print("=" * 72)
    novo = csm3rom.load_rom(out_path)
    arc = csm3rom.open_archive(novo, csm3rom.SCRIPT_ARCHIVE)
    ok = bad = 0
    for entry in arc.entries:
        if entry.is_empty:
            continue
        try:
            s = csm3rom.load_script(arc, entry.index)
            if s is None:
                continue
            verify_rebuilt(entry.index, bytes(s.body), auto_map)
            ok += 1
        except (ValueError, lz77.Lz77Error, InjectError) as exc:
            bad += 1
            if bad <= 5:
                print(f"      script {entry.index}: {exc}")
    print(f"  scripts relidos e validados: {ok:,}")
    print(f"  falhas                     : {bad:,}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
