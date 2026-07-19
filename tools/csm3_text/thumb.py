"""Interpretador de ARM Thumb, o suficiente para executar o blitter da fonte.

Duas tentativas de VWF falharam porque eu deduzi o comportamento do blitter
lendo assembly. O emulador nao me deu depurador utilizavel. Mas o blitter e uma
FUNCAO PURA - recebe ponteiros e escreve memoria, sem tocar em hardware. Entao
da para executa-la aqui e observar cada escrita.

Implementa apenas o subconjunto que o blitter usa. Qualquer instrucao fora dele
levanta excecao em vez de executar errado silenciosamente.
"""

from __future__ import annotations

import struct


class ThumbError(RuntimeError):
    pass


class Memoria:
    """Memoria esparsa por regiao, com registro de escritas."""

    def __init__(self):
        self.regioes: list[tuple[int, bytearray]] = []
        self.escritas: list[tuple[int, int, int]] = []   # (endereco, tamanho, valor)

    def mapear(self, base: int, dados: bytes | bytearray) -> None:
        self.regioes.append((base, bytearray(dados)))

    def _achar(self, endereco: int, tamanho: int):
        for base, dados in self.regioes:
            if base <= endereco and endereco + tamanho <= base + len(dados):
                return dados, endereco - base
        raise ThumbError(f"acesso fora do mapeado: 0x{endereco:08X} ({tamanho}b)")

    def ler(self, endereco: int, tamanho: int) -> int:
        dados, off = self._achar(endereco, tamanho)
        return int.from_bytes(dados[off:off + tamanho], "little")

    def escrever(self, endereco: int, tamanho: int, valor: int) -> None:
        dados, off = self._achar(endereco, tamanho)
        dados[off:off + tamanho] = (valor & ((1 << (tamanho * 8)) - 1)).to_bytes(
            tamanho, "little")
        self.escritas.append((endereco, tamanho, valor))


class Cpu:
    def __init__(self, mem: Memoria):
        self.mem = mem
        self.r = [0] * 16
        self.n = self.z = self.c = self.v = False
        self.passos = 0
        self.limite = 200_000

    # --- utilidades ---------------------------------------------------------
    @staticmethod
    def _u32(v: int) -> int:
        return v & 0xFFFFFFFF

    def _flags_nz(self, v: int) -> int:
        v = self._u32(v)
        self.n = bool(v & 0x80000000)
        self.z = v == 0
        return v

    def executar(self, inicio: int, retorno: int = 0xFFFFFFF0) -> None:
        """Executa a partir de `inicio` ate o PC virar `retorno` (lr sentinela)."""
        self.r[15] = inicio & ~1
        self.r[14] = retorno
        while True:
            if self.r[15] == (retorno & ~1) or self.r[15] == retorno:
                return
            self.passos += 1
            if self.passos > self.limite:
                raise ThumbError(f"passou de {self.limite} instrucoes - laco infinito?")
            pc = self.r[15]
            op = self.mem.ler(pc, 2)
            self.r[15] = pc + 2
            self._executar_uma(op, pc)

    # --- decodificacao ------------------------------------------------------
    def _executar_uma(self, op: int, pc: int) -> None:
        top = op >> 11

        # 000xx: lsl/lsr/asr imediato
        if top in (0b00000, 0b00001, 0b00010):
            imm = (op >> 6) & 0x1F
            rs, rd = (op >> 3) & 7, op & 7
            v = self.r[rs]
            if top == 0b00000:      # lsl
                if imm:
                    self.c = bool((v >> (32 - imm)) & 1)
                    v = self._u32(v << imm)
            elif top == 0b00001:    # lsr
                imm = imm or 32
                self.c = bool((v >> (imm - 1)) & 1) if imm <= 32 else False
                v = v >> imm if imm < 32 else 0
            else:                   # asr
                imm = imm or 32
                sv = v - (1 << 32) if v & 0x80000000 else v
                v = self._u32(sv >> min(imm, 31))
            self.r[rd] = self._flags_nz(v)
            return

        # 00011: add/sub registrador ou imediato de 3 bits
        if top == 0b00011:
            i = (op >> 10) & 1
            sub = (op >> 9) & 1
            rn = (op >> 6) & 7
            rs, rd = (op >> 3) & 7, op & 7
            b = rn if i else self.r[rn]
            a = self.r[rs]
            res = a - b if sub else a + b
            self.c = (a >= b) if sub else (res > 0xFFFFFFFF)
            self.r[rd] = self._flags_nz(res)
            return

        # 001xx: mov/cmp/add/sub imediato de 8 bits
        if top >> 2 == 0b001:
            modo = (op >> 11) & 3
            rd = (op >> 8) & 7
            imm = op & 0xFF
            if modo == 0:           # mov
                self.r[rd] = self._flags_nz(imm)
            elif modo == 1:         # cmp
                a = self.r[rd]
                self.c = a >= imm
                self._flags_nz(a - imm)
            elif modo == 2:         # add
                a = self.r[rd]
                res = a + imm
                self.c = res > 0xFFFFFFFF
                self.r[rd] = self._flags_nz(res)
            else:                   # sub
                a = self.r[rd]
                self.c = a >= imm
                self.r[rd] = self._flags_nz(a - imm)
            return

        # 010000: operacoes ALU registrador-registrador
        if op >> 10 == 0b010000:
            sub = (op >> 6) & 0xF
            rs, rd = (op >> 3) & 7, op & 7
            a, b = self.r[rd], self.r[rs]
            if sub == 0x0:          # and
                self.r[rd] = self._flags_nz(a & b)
            elif sub == 0x1:        # eor
                self.r[rd] = self._flags_nz(a ^ b)
            elif sub == 0x2:        # lsl registrador
                n = b & 0xFF
                self.r[rd] = self._flags_nz(self._u32(a << n) if n < 32 else 0)
            elif sub == 0x3:        # lsr registrador
                n = b & 0xFF
                self.r[rd] = self._flags_nz(a >> n if n < 32 else 0)
            elif sub == 0x8:        # tst
                self._flags_nz(a & b)
            elif sub == 0xA:        # cmp
                self.c = a >= b
                self._flags_nz(a - b)
            elif sub == 0xC:        # orr
                self.r[rd] = self._flags_nz(a | b)
            elif sub == 0xD:        # mul
                self.r[rd] = self._flags_nz(a * b)
            elif sub == 0xE:        # bic
                self.r[rd] = self._flags_nz(a & ~b)
            elif sub == 0xF:        # mvn
                self.r[rd] = self._flags_nz(~b)
            else:
                raise ThumbError(f"ALU sub={sub:X} em 0x{pc:08X}")
            return

        # 010001: operacoes com registradores altos e bx
        if op >> 10 == 0b010001:
            sub = (op >> 8) & 3
            h1, h2 = (op >> 7) & 1, (op >> 6) & 1
            rd = (op & 7) | (h1 << 3)
            rs = ((op >> 3) & 7) | (h2 << 3)
            if sub == 0:            # add
                self.r[rd] = self._u32(self.r[rd] + self.r[rs])
            elif sub == 1:          # cmp
                a, b = self.r[rd], self.r[rs]
                self.c = a >= b
                self._flags_nz(a - b)
            elif sub == 2:          # mov
                self.r[rd] = self.r[rs]
            else:                   # bx
                self.r[15] = self.r[rs] & ~1
            return

        # 01001: ldr literal (relativo ao PC)
        if op >> 11 == 0b01001:
            rd = (op >> 8) & 7
            imm = (op & 0xFF) << 2
            base = (pc + 4) & ~3
            self.r[rd] = self.mem.ler(base + imm, 4)
            return

        # 0101: load/store com registrador de offset
        if op >> 12 == 0b0101:
            ro = (op >> 6) & 7
            rb, rd = (op >> 3) & 7, op & 7
            end = self._u32(self.r[rb] + self.r[ro])
            codigo = (op >> 9) & 7
            if codigo == 0:         # str
                self.mem.escrever(end, 4, self.r[rd])
            elif codigo == 1:       # strh
                self.mem.escrever(end, 2, self.r[rd] & 0xFFFF)
            elif codigo == 2:       # strb
                self.mem.escrever(end, 1, self.r[rd] & 0xFF)
            elif codigo == 4:       # ldr
                self.r[rd] = self.mem.ler(end, 4)
            elif codigo == 5:       # ldrh
                self.r[rd] = self.mem.ler(end, 2)
            elif codigo == 6:       # ldrb
                self.r[rd] = self.mem.ler(end, 1)
            elif codigo == 3:       # ldrsb
                v = self.mem.ler(end, 1)
                self.r[rd] = self._u32(v - 256 if v & 0x80 else v)
            elif codigo == 7:       # ldrsh
                v = self.mem.ler(end, 2)
                self.r[rd] = self._u32(v - 65536 if v & 0x8000 else v)
            return

        # 011: load/store com offset imediato (palavra/byte)
        if op >> 13 == 0b011:
            b = (op >> 12) & 1
            l = (op >> 11) & 1
            imm = (op >> 6) & 0x1F
            rb, rd = (op >> 3) & 7, op & 7
            passo = 1 if b else 4
            end = self._u32(self.r[rb] + imm * passo)
            if l:
                self.r[rd] = self.mem.ler(end, passo)
            else:
                self.mem.escrever(end, passo, self.r[rd])
            return

        # 1000: load/store halfword imediato
        if op >> 12 == 0b1000:
            l = (op >> 11) & 1
            imm = ((op >> 6) & 0x1F) * 2
            rb, rd = (op >> 3) & 7, op & 7
            end = self._u32(self.r[rb] + imm)
            if l:
                self.r[rd] = self.mem.ler(end, 2)
            else:
                self.mem.escrever(end, 2, self.r[rd] & 0xFFFF)
            return

        # 1001: load/store relativo a SP
        if op >> 12 == 0b1001:
            l = (op >> 11) & 1
            rd = (op >> 8) & 7
            imm = (op & 0xFF) << 2
            end = self._u32(self.r[13] + imm)
            if l:
                self.r[rd] = self.mem.ler(end, 4)
            else:
                self.mem.escrever(end, 4, self.r[rd])
            return

        # 1010: add rd, pc/sp, imm
        if op >> 12 == 0b1010:
            sp = (op >> 11) & 1
            rd = (op >> 8) & 7
            imm = (op & 0xFF) << 2
            base = self.r[13] if sp else ((pc + 4) & ~3)
            self.r[rd] = self._u32(base + imm)
            return

        # 10110000: add/sub sp, imm
        if op >> 8 == 0b10110000:
            imm = (op & 0x7F) << 2
            self.r[13] = self._u32(self.r[13] - imm if op & 0x80 else self.r[13] + imm)
            return

        # 1011x10x: push/pop
        if (op >> 12) == 0b1011 and ((op >> 9) & 3) == 0b10:
            l = (op >> 11) & 1
            r_bit = (op >> 8) & 1
            lista = [i for i in range(8) if op & (1 << i)]
            if l:                    # pop
                for i in lista:
                    self.r[i] = self.mem.ler(self.r[13], 4)
                    self.r[13] += 4
                if r_bit:
                    self.r[15] = self.mem.ler(self.r[13], 4) & ~1
                    self.r[13] += 4
            else:                    # push
                if r_bit:
                    self.r[13] -= 4
                    self.mem.escrever(self.r[13], 4, self.r[14])
                for i in reversed(lista):
                    self.r[13] -= 4
                    self.mem.escrever(self.r[13], 4, self.r[i])
            return

        # 1100: stm/ldm
        if op >> 12 == 0b1100:
            l = (op >> 11) & 1
            rb = (op >> 8) & 7
            lista = [i for i in range(8) if op & (1 << i)]
            end = self.r[rb]
            for i in lista:
                if l:
                    self.r[i] = self.mem.ler(end, 4)
                else:
                    self.mem.escrever(end, 4, self.r[i])
                end += 4
            self.r[rb] = self._u32(end)
            return

        # 1101: salto condicional
        if op >> 12 == 0b1101:
            cond = (op >> 8) & 0xF
            off = op & 0xFF
            off = off - 256 if off & 0x80 else off
            tabela = {
                0x0: self.z, 0x1: not self.z,
                0x2: self.c, 0x3: not self.c,
                0x4: self.n, 0x5: not self.n,
                0x8: self.c and not self.z, 0x9: (not self.c) or self.z,
                0xA: self.n == self.v, 0xB: self.n != self.v,
                0xC: (not self.z) and (self.n == self.v),
                0xD: self.z or (self.n != self.v),
                0xE: True,
            }
            if cond not in tabela:
                raise ThumbError(f"condicao {cond:X} em 0x{pc:08X}")
            if tabela[cond]:
                self.r[15] = self._u32(pc + 4 + off * 2)
            return

        # 11100: salto incondicional
        if op >> 11 == 0b11100:
            off = op & 0x7FF
            off = off - 2048 if off & 0x400 else off
            self.r[15] = self._u32(pc + 4 + off * 2)
            return

        # 1111: bl (dois halfwords)
        if op >> 12 == 0b1111:
            alto = (op >> 11) & 1
            if not alto:
                off = op & 0x7FF
                off = off - 2048 if off & 0x400 else off
                self.r[14] = self._u32(pc + 4 + (off << 12))
                return
            proximo = op & 0x7FF
            destino = self._u32(self.r[14] + (proximo << 1))
            self.r[14] = (pc + 2) | 1
            self.r[15] = destino & ~1
            return

        raise ThumbError(f"instrucao 0x{op:04X} nao implementada em 0x{pc:08X}")
