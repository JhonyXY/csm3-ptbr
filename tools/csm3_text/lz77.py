"""Compressao LZ77 da BIOS da GBA (tipo 0x10), usada pelos blobs do archive 2.

Formato do cabecalho:
    byte 0      : 0x10 (identificador do tipo)
    bytes 1..3  : tamanho descomprimido, 24 bits little-endian

Depois vem uma sequencia de blocos. Cada bloco tem 1 byte de flags seguido de
ate 8 unidades. Os bits de flag sao lidos do MSB para o LSB; bit setado indica
uma referencia comprimida (2 bytes), bit zerado indica um literal (1 byte).

Referencia comprimida:
    byte0 = (comprimento - 3) << 4 | (distancia - 1) >> 8
    byte1 = (distancia - 1) & 0xFF
"""

from __future__ import annotations


class Lz77Error(ValueError):
    pass


def decompress(data: bytes, offset: int = 0) -> bytes:
    """Descomprime um bloco LZ77 comecando em `offset`."""
    if offset + 4 > len(data):
        raise Lz77Error(f"cabecalho truncado em 0x{offset:X}")
    if data[offset] != 0x10:
        raise Lz77Error(
            f"tipo de compressao 0x{data[offset]:02X} em 0x{offset:X}, esperado 0x10"
        )

    size = data[offset + 1] | (data[offset + 2] << 8) | (data[offset + 3] << 16)
    src = offset + 4
    out = bytearray()

    while len(out) < size:
        if src >= len(data):
            raise Lz77Error(f"stream truncado (obtidos {len(out)} de {size} bytes)")
        flags = data[src]
        src += 1

        for bit in range(7, -1, -1):
            if len(out) >= size:
                break
            if not (flags >> bit) & 1:
                out.append(data[src])
                src += 1
                continue

            if src + 1 >= len(data):
                raise Lz77Error("referencia truncada")
            b0, b1 = data[src], data[src + 1]
            src += 2
            length = (b0 >> 4) + 3
            disp = (((b0 & 0x0F) << 8) | b1) + 1
            if disp > len(out):
                raise Lz77Error(
                    f"distancia {disp} maior que a saida atual ({len(out)} bytes)"
                )
            start = len(out) - disp
            # Copia byte a byte de proposito: as referencias podem se sobrepor
            # a saida ainda em construcao (padrao de repeticao).
            for i in range(length):
                out.append(out[start + i])

    return bytes(out[:size])


def compress(data: bytes, *, min_match: int = 3, max_match: int = 18) -> bytes:
    """Comprime no formato LZ77 da GBA.

    Nao busca reproduzir o compressor original byte a byte - o objetivo e gerar
    um stream valido e razoavelmente compacto. A janela e limitada a 4096 bytes
    e o casamento a 18 bytes, que sao os limites do formato.
    """
    if len(data) > 0xFFFFFF:
        raise Lz77Error(f"{len(data)} bytes excede o maximo de 24 bits do formato")

    out = bytearray()
    out.append(0x10)
    out += len(data).to_bytes(3, "little")

    # Indice de posicoes por trinca de bytes, para achar candidatos rapido.
    positions: dict[bytes, list[int]] = {}
    pos = 0
    n = len(data)

    while pos < n:
        flag_index = len(out)
        out.append(0)
        flags = 0

        for bit in range(7, -1, -1):
            if pos >= n:
                break

            best_len = 0
            best_disp = 0
            if pos + min_match <= n:
                key = data[pos : pos + min_match]
                window_start = max(0, pos - 4096)
                for cand in reversed(positions.get(key, ())):
                    if cand < window_start:
                        break
                    length = 0
                    limit = min(max_match, n - pos)
                    while length < limit and data[cand + length] == data[pos + length]:
                        length += 1
                    if length > best_len:
                        best_len = length
                        best_disp = pos - cand
                        if length == max_match:
                            break

            if best_len >= min_match:
                flags |= 1 << bit
                enc = ((best_len - 3) << 4) | ((best_disp - 1) >> 8)
                out.append(enc & 0xFF)
                out.append((best_disp - 1) & 0xFF)
                advance = best_len
            else:
                out.append(data[pos])
                advance = 1

            for i in range(advance):
                p = pos + i
                if p + min_match <= n:
                    positions.setdefault(data[p : p + min_match], []).append(p)
            pos += advance

        out[flag_index] = flags

    # A BIOS espera o stream alinhado em 4 bytes.
    while len(out) % 4:
        out.append(0)
    return bytes(out)
