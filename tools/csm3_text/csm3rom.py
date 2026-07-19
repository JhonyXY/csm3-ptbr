"""Acesso aos archives da ROM do csm3.

O jogo guarda seus dados em 5 archives, resolvidos em runtime por
`sub_08001D3C(archive, indice)` (ver src/main.c:489). Cada archive tem o
formato:

    +0x00  u16 count      quantidade de entradas
    +0x02  u16 version    sempre 1
    +0x04  u32            sempre 4
    +0x08  entradas[count], 8 bytes cada:
               u32 offset  em unidades de 16 bytes, relativo a base do archive
               u32 size    em unidades de 16 bytes

Entradas com size 0 sao slots vazios.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import lz77

# Offsets dentro do arquivo baserom.gba (endereco GBA menos 0x08000000).
ARCHIVE_OFFSETS = {
    0: 0x0BDA40C,
    1: 0x18C8D9C,
    2: 0x1718FFC,  # scripts e texto
    3: 0x14D446C,  # fonte
    4: 0x1E2261C,
}

SCRIPT_ARCHIVE = 2
FONT_ARCHIVE = 3

PSI3_MAGIC = b"PSI3"
PSI3_HEADER_SIZE = 0x10


@dataclass(frozen=True)
class Entry:
    index: int
    offset: int  # offset absoluto no arquivo da ROM
    size: int  # tamanho em bytes

    @property
    def is_empty(self) -> bool:
        return self.size == 0


class Archive:
    def __init__(self, rom: bytes, base: int, number: int | None = None):
        self.rom = rom
        self.base = base
        self.number = number

        count, version = struct.unpack_from("<HH", rom, base)
        marker = struct.unpack_from("<I", rom, base + 4)[0]
        if version != 1:
            raise ValueError(f"archive em 0x{base:X}: version {version}, esperado 1")
        if marker != 4:
            raise ValueError(f"archive em 0x{base:X}: marker {marker}, esperado 4")

        self.count = count
        self.entries: list[Entry] = []
        for i in range(count):
            off, size = struct.unpack_from("<II", rom, base + 8 + i * 8)
            self.entries.append(
                Entry(index=i, offset=base + off * 16, size=size * 16)
            )

    def __len__(self) -> int:
        return self.count

    def raw(self, index: int) -> bytes:
        e = self.entries[index]
        return self.rom[e.offset : e.offset + e.size]

    def used(self) -> list[Entry]:
        return [e for e in self.entries if not e.is_empty]


@dataclass
class Script:
    """Um blob do archive 2, ja descomprimido e sem o cabecalho PSI3."""

    index: int
    header: bytes  # os 0x10 bytes do cabecalho PSI3
    body: bytearray  # bytecode, offset 0 aqui == offset 0x10 no blob

    @property
    def declared_size(self) -> int:
        return struct.unpack_from("<I", self.header, 4)[0]

    def to_blob(self) -> bytes:
        header = bytearray(self.header)
        struct.pack_into("<I", header, 4, PSI3_HEADER_SIZE + len(self.body))
        return bytes(header) + bytes(self.body)


def load_rom(path: str | Path) -> bytes:
    data = Path(path).read_bytes()
    if len(data) != 33554432:
        raise ValueError(f"{path}: {len(data)} bytes, esperado 33554432 (32 MiB)")
    return data


def open_archive(rom: bytes, number: int) -> Archive:
    return Archive(rom, ARCHIVE_OFFSETS[number], number)


def load_script(archive: Archive, index: int) -> Script | None:
    """Descomprime o blob `index` e valida o cabecalho PSI3.

    Retorna None para slots vazios.
    """
    entry = archive.entries[index]
    if entry.is_empty:
        return None

    blob = lz77.decompress(archive.rom, entry.offset)
    if blob[:4] != PSI3_MAGIC:
        raise ValueError(f"script {index}: magic {blob[:4]!r}, esperado {PSI3_MAGIC!r}")

    declared = struct.unpack_from("<I", blob, 4)[0]
    if declared != len(blob):
        raise ValueError(
            f"script {index}: cabecalho declara {declared} bytes, blob tem {len(blob)}"
        )

    return Script(
        index=index,
        header=blob[:PSI3_HEADER_SIZE],
        body=bytearray(blob[PSI3_HEADER_SIZE:]),
    )


def iter_scripts(rom: bytes):
    """Itera sobre todos os scripts nao-vazios do archive 2."""
    archive = open_archive(rom, SCRIPT_ARCHIVE)
    for entry in archive.entries:
        if entry.is_empty:
            continue
        script = load_script(archive, entry.index)
        if script is not None:
            yield script
