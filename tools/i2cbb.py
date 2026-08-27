#!/usr/bin/env python3
# Битбанг-I2C по TLMM (/dev/mem) для sm5703 @0x49: SDA=GPIO18, SCL=GPIO19
# usage: i2cbb.py w <reg> <val> | i2cbb.py r <reg>
import sys, mmap, os, time
TLMM = 0x01000000
SDA, SCL = 18, 19
fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
maps = {}
def m(pin):
    if pin not in maps:
        maps[pin] = mmap.mmap(fd, 0x1000, offset=TLMM + 0x1000 * pin)
    return maps[pin]
def cfg(pin, oe, pull):
    mm = m(pin)
    v = int.from_bytes(mm[0:4], "little")
    v &= ~((1 << 9) | 0xf << 2 | 3)   # oe, func, pull
    v |= (oe << 9) | pull              # func=0
    mm[0:4] = v.to_bytes(4, "little")
def out0(pin):   # тянем в 0
    mm = m(pin); mm[4:8] = (0).to_bytes(4, "little"); cfg(pin, 1, 0)
def rel(pin):    # отпускаем (вход, внешняя подтяжка)
    cfg(pin, 0, 3)
def rd(pin):
    return int.from_bytes(m(pin)[4:8], "little") & 1
D = 0.00002
def dly(): time.sleep(D)
def start():
    rel(SDA); rel(SCL); dly()
    out0(SDA); dly(); out0(SCL); dly()
def stop():
    out0(SDA); dly(); rel(SCL); dly(); rel(SDA); dly()
def wbit(b):
    (rel if b else out0)(SDA); dly()
    rel(SCL); dly(); out0(SCL); dly()
def rbit():
    rel(SDA); dly(); rel(SCL); dly()
    b = rd(SDA); out0(SCL); dly()
    return b
def wbyte(x):
    for i in range(7, -1, -1):
        wbit((x >> i) & 1)
    return rbit() == 0   # ACK
def rbyte(ack):
    x = 0
    for _ in range(8):
        x = (x << 1) | rbit()
    wbit(0 if ack else 1)
    return x
ADDR = 0x49
op = sys.argv[1]
reg = int(sys.argv[2], 0)
if op == "w":
    val = int(sys.argv[3], 0)
    start()
    a1 = wbyte(ADDR << 1); a2 = wbyte(reg); a3 = wbyte(val)
    stop()
    print("w %02x=%02x ack=%d%d%d" % (reg, val, a1, a2, a3))
else:
    start()
    a1 = wbyte(ADDR << 1); a2 = wbyte(reg)
    start()
    a3 = wbyte((ADDR << 1) | 1)
    v = rbyte(False)
    stop()
    print("r %02x=0x%02x ack=%d%d%d" % (reg, v, a1, a2, a3))
