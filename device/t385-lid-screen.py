#!/usr/bin/python3
# SM-T385: гасим экран по датчику чехла (SW_LID из gpio-keys).
# logind по крышке лишь блокирует сессию (HandleLidSwitch=lock, потому
# что suspend на порте не отлажен), а подсветку он не трогает. Этот
# сторож слушает SW_LID и дёргает скринсейвер phosh: закрыт -> экран
# погашен, открыт -> проснулся.
import glob, os, select, struct, subprocess, time

FMT = "llHHi"
SZ = struct.calcsize(FMT)
EV_SW, SW_LID = 0x05, 0x00
LOG = "/tmp/lid-screen.log"

def log(msg):
    with open(LOG, "a") as f:
        f.write("%.1f %s\n" % (time.time(), msg))

def find_dev():
    for d in glob.glob("/sys/class/input/input*"):
        try:
            if open(d + "/name").read().strip() == "gpio-keys":
                ev = [e for e in os.listdir(d) if e.startswith("event")]
                if ev:
                    return "/dev/input/" + ev[0]
        except OSError:
            pass
    return None

def screensaver(active):
    subprocess.Popen(
        ["sudo", "-u", "user", "env",
         "XDG_RUNTIME_DIR=/run/user/10000",
         "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/10000/bus",
         "timeout", "5", "busctl", "--user", "call",
         "org.gnome.ScreenSaver", "/org/gnome/ScreenSaver",
         "org.gnome.ScreenSaver", "SetActive", "b",
         "true" if active else "false"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

dev = None
while dev is None:
    dev = find_dev()
    if dev is None:
        time.sleep(2)
log("старт, устройство: %s" % dev)
fd = os.open(dev, os.O_RDONLY)
while True:
    select.select([fd], [], [])
    data = os.read(fd, SZ * 8)
    for off in range(0, len(data) - SZ + 1, SZ):
        _, _, etype, code, value = struct.unpack_from(FMT, data, off)
        if etype == EV_SW and code == SW_LID:
            log("крышка %s" % ("закрыта" if value else "открыта"))
            screensaver(bool(value))
