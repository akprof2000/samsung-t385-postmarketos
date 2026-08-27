#!/usr/bin/python3
"""Убирает цветные полосы из ПРОВЕРЕННОГО образа lk2nd, не пересобирая его.

Полосы рисуют отладочные «пиксельные маркеры»: короткие циклы, каждый
из которых заливает 64 КБ кадрового буфера цветом. Пересобрать lk2nd из
исходников не удаётся (свежая сборка не стартует — см. README), поэтому
правим уже проверенный образ.

Способ: в каждом таком цикле инструкция записи
        str  rZ, [rX], #4
заменяется на
        add  rX, rX, #4
— указатель по-прежнему двигается, цикл завершается как раньше, но в
кадровый буфер ничего не пишется. Длина кода не меняется ни на байт,
поэтому раскладка и тайминги остаются в точности как в рабочем образе.

Просто «занопить» запись нельзя: пост-инкремент указателя живёт в самой
инструкции str, и без него цикл стал бы бесконечным. Переносить запись
по другому адресу тоже нельзя — за пределами кадрового буфера стоит
защита памяти (XPU), и планшет виснет наглухо.

Использование:
    python3 patch_stripes.py lk2nd-working.img lk2nd-clean.img
"""
import hashlib
import re
import struct
import subprocess
import sys
import tempfile

LOAD_ADDR = 0x8F600000          # база, куда lk2nd релоцируется
FB_HI = (0xA81A, 0xA81E, 0xA822, 0xA826, 0xA82A, 0xA82E)  # старшие半 адресов маркеров


def unpack_img(data):
    """границы тела lk внутри Android boot image"""
    assert data[:8] == b"ANDROID!", "не Android boot image"
    ksize, = struct.unpack_from("<I", data, 8)
    psize, = struct.unpack_from("<I", data, 36)
    first_dtb = data.find(bytes.fromhex("d00dfeed"), psize, psize + ksize)
    end = first_dtb if first_dtb > 0 else psize + ksize
    return psize, end


def disasm(body):
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(body)
        path = f.name
    out = subprocess.run(
        ["arm-none-eabi-objdump", "-D", "-b", "binary", "-m", "arm",
         "--adjust-vma=%#x" % LOAD_ADDR, path],
        capture_output=True, text=True, check=True).stdout
    return out.splitlines()


LINE = re.compile(r"^\s*([0-9a-f]+):\s+([0-9a-f]{8})\s+(.*)$")
STR_POST = re.compile(r"str\s+r(\d+), \[r(\d+)\], #4")


def find_stores(lines):
    """адреса инструкций str внутри маркерных циклов"""
    found = []
    for i, line in enumerate(lines):
        m = LINE.match(line)
        if not m:
            continue
        text = m.group(3)
        # признак маркера: загрузка старшей половины адреса кадрового буфера
        hit = ("movt" in text and
               any(("%#x" % hi) in text.lower() for hi in FB_HI))
        # маркер в crt0: заливка белым через mvn + счётчик 0x4000
        crt0 = "mvn" in text and "#0" == text.split(",")[-1].strip()
        if not (hit or crt0):
            continue
        for j in range(i + 1, min(i + 14, len(lines))):
            m2 = LINE.match(lines[j])
            if not m2:
                continue
            s = STR_POST.search(m2.group(3))
            if s:
                addr = int(m2.group(1), 16)
                rt, rn = int(s.group(1)), int(s.group(2))
                if all(a != addr for a, _, _ in found):
                    found.append((addr, rt, rn))
                break
    return found


def fix_id(data):
    """пересчитать SHA1 в заголовке (mkbootimg пишет его туда)"""
    ks, = struct.unpack_from("<I", data, 8)
    rs, = struct.unpack_from("<I", data, 16)
    ss, = struct.unpack_from("<I", data, 24)
    ps, = struct.unpack_from("<I", data, 36)
    dts, = struct.unpack_from("<I", data, 40)
    pg = lambda n: (n + ps - 1) // ps * ps
    off = ps
    parts = []
    for size in (ks, rs, ss):
        parts.append((bytes(data[off:off + size]), size))
        off += pg(size)
    if dts:
        parts.append((bytes(data[off:off + dts]), dts))
    h = hashlib.sha1()
    for blob, size in parts:
        h.update(blob)
        h.update(struct.pack("<I", size))
    data[576:596] = h.digest()
    data[596:608] = b"\0" * 12


def main():
    src, dst = sys.argv[1], sys.argv[2]
    data = bytearray(open(src, "rb").read())
    start, end = unpack_img(data)
    body = bytes(data[start:end])
    print("тело lk: %d байт" % len(body))

    stores = find_stores(disasm(body))
    if not stores:
        sys.exit("маркерных циклов не найдено — образ уже чист?")

    for addr, rt, rn in stores:
        off = start + (addr - LOAD_ADDR)
        old, = struct.unpack_from("<I", data, off)
        assert old == (0xE4800004 | (rn << 16) | (rt << 12)), \
            "не та инструкция по %#x: %#x" % (addr, old)
        new = 0xE2800004 | (rn << 16) | (rn << 12)   # add rN, rN, #4
        struct.pack_into("<I", data, off, new)
        print("  %#x: str r%d, [r%d], #4  ->  add r%d, r%d, #4"
              % (addr, rt, rn, rn, rn))

    fix_id(data)
    open(dst, "wb").write(bytes(data))
    print("записано %s (%d байт), маркеров обезврежено: %d"
          % (dst, len(data), len(stores)))


if __name__ == "__main__":
    main()
