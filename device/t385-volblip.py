#!/usr/bin/python3
# SM-T385: оболочка меняет громкость без звука. Сторож слушает кнопки
# громкости (KEY_VOLUMEDOWN=114 на линии resin/event1, KEY_VOLUMEUP=115
# на gpio-keys/event2) и играет системный блямк через canberra —
# у feedbackd для audio-volume-change звука нет вовсе.
import struct, select, subprocess, time, os

DEVS = ["/dev/input/event1", "/dev/input/event2"]
FMT = "llHHi"
SZ = struct.calcsize(FMT)
LOG = "/tmp/volblip.log"

def log(msg):
    with open(LOG, "a") as f:
        f.write("%.1f %s\n" % (time.time(), msg))

fds = {}
for d in DEVS:
    try:
        fds[os.open(d, os.O_RDONLY)] = d
    except OSError as e:
        log("open %s: %s" % (d, e))

log("старт, устройства: %s" % list(fds.values()))
last = 0.0
while fds:
    r, _, _ = select.select(list(fds), [], [])
    for fd in r:
        data = os.read(fd, SZ * 8)
        for off in range(0, len(data) - SZ + 1, SZ):
            _, _, etype, code, value = struct.unpack_from(FMT, data, off)
            if etype == 1 and code in (114, 115) and value == 1:
                log("кнопка %d" % code)
                now = time.monotonic()
                if now - last > 0.25:
                    last = now
                    subprocess.Popen(
                        ["sudo", "-u", "user", "env",
                         "XDG_RUNTIME_DIR=/run/user/10000",
                         "DBUS_SESSION_BUS_ADDRESS="
                         "unix:path=/run/user/10000/bus",
                         "timeout", "3", "canberra-gtk-play",
                         "-i", "audio-volume-change"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
