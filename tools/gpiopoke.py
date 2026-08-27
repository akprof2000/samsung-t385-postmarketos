#!/usr/bin/env python3
# TLMM MSM8917: чтение/запись GPIO через /dev/mem
# usage: gpiopoke.py <gpio> [0|1|read]
import sys, mmap, os
TLMM = 0x01000000
pin = int(sys.argv[1])
op = sys.argv[2] if len(sys.argv) > 2 else "read"
fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
base = TLMM + 0x1000 * pin
m = mmap.mmap(fd, 0x1000, offset=base)
def r32(off): return int.from_bytes(m[off:off+4], "little")
def w32(off, v): m[off:off+4] = v.to_bytes(4, "little")
cfg = r32(0)
io = r32(4)
if op == "read":
    print(f"gpio{pin}: cfg={cfg:#x} (func={(cfg>>2)&0xf} oe={(cfg>>9)&1}) in={io&1} out={(io>>1)&1}")
else:
    v = int(op)
    w32(4, v << 1)
    print(f"gpio{pin}: out={v}")
m.close(); os.close(fd)
