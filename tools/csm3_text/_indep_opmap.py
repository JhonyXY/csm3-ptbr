import struct
rom = open('/home/jhony/decomps/csm3/baserom.gba','rb').read()

# hi=0x03 -> unk0=5 -> sub_0801316C -> gUnk_08B718B0
BASE = 0xB718B0
END  = 0xB71AEC
print("tabela gUnk_08B718B0: %d entradas" % ((END-BASE)//4))

expect = {
    0x7C: 'sub_0806F6C4',
    0x53: 'sub_0808F0C0',
    0x50: 'sub_0808F474',
    0x54: 'sub_0808F4B0',
    0x5B: 'sub_08093648',
    0x5E: 'sub_080936A8',
}
for idx in sorted(expect):
    off = BASE + idx*4
    assert off < END, "indice fora da tabela"
    p = struct.unpack_from('<I', rom, off)[0]
    got = 'sub_%08X' % (p & ~1)
    ok = 'OK ' if got == expect[idx] else '*** MISMATCH ***'
    print("  [0x%02X] rom=%08X -> %-16s esperado %-16s %s"
          % (idx, p, got, expect[idx], ok))

# quais outros indices apontam para os mesmos handlers? (opcodes alternativos)
rev = {}
for i in range((END-BASE)//4):
    p = struct.unpack_from('<I', rom, BASE + i*4)[0]
    rev.setdefault('sub_%08X' % (p & ~1), []).append(i)
print("\nindices que apontam para cada handler (todas as tabelas hi=0x03):")
for name in sorted(set(expect.values())):
    print("  %-16s -> %s" % (name, ['0x%02X' % i for i in rev.get(name, [])]))

# checar tambem as outras 4 tabelas por aliases
TABLES = {0x01:(0xB716F4,0xB71750), 0x02:(0xB71750,0xB718B0),
          0x03:(0xB718B0,0xB71AEC), 0x04:(0xB71AEC,0xB71AEC+0x100),
          0x00:(0xB716B4,0xB716F4)}
print("\nbusca de aliases em TODAS as tabelas:")
for hi,(b,e) in sorted(TABLES.items()):
    for i in range((e-b)//4):
        p = struct.unpack_from('<I', rom, b + i*4)[0]
        n = 'sub_%08X' % (p & ~1)
        if n in set(expect.values()):
            print("  hi=0x%02X[0x%02X] -> %s" % (hi, i, n))
