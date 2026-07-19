"""0x0218: separa ocorrencias que PODEM ser instrucao (palavra anterior nao e
token de push 1/2/3, logo 0x0218 nao pode ser o valor imediato/indice dele)."""
from __future__ import annotations
import struct, sys
sys.path.insert(0, '/home/jhony/decomps/csm3/tools/csm3_text')
import csm3rom

ROM = csm3rom.load_rom('/home/jhony/decomps/csm3/baserom.gba')
scripts = [s for s in csm3rom.iter_scripts(ROM) if s is not None]
PUSH = {1, 2, 3}

for s in scripts:
    body = bytes(s.body)
    for off in range(0, len(body) - 1, 2):
        if struct.unpack_from('<H', body, off)[0] != 0x0218:
            continue
        prev = struct.unpack_from('<H', body, off - 2)[0] if off >= 2 else None
        if prev in PUSH:
            continue  # 0x0218 e o operando do push anterior -> falso positivo
        lo = max(0, off - 8)
        words = [struct.unpack_from('<H', body, x)[0]
                 for x in range(lo, min(len(body) - 1, off + 20), 2)]
        mk = (off - lo) // 2
        txt = ' '.join(('[%04X]' % w) if i == mk else ('%04X' % w)
                       for i, w in enumerate(words))
        print(f'script {s.index} @0x{off:04X} prev={prev if prev is None else "0x%04X"%prev}: {txt}')
