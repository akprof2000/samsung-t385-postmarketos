#!/usr/bin/python3
"""Включает звук разговора на время звонка (SM-T385).

Разговорный тракт живёт внутри звукового сопроцессора: модем и кодек
соединяются там напрямую, минуя систему. Сопроцессор поднимает тракт в
момент, когда кто-то ОТКРЫВАЕТ голосовой поток VoiceMMode1 (в драйвере
q6voice это делает startup у DAI), и роняет при закрытии. Само по себе
ничто его не открывает: ModemManager занимается сигнализацией,
callaudiod — только переключением UCM. Отсюда и тишина в обе стороны
при исправном соединении.

Служба следит за вызовами у ModemManager и держит поток открытым, пока
идёт разговор. Данные через поток НЕ передаются — их там и не ждут
(попытка записи возвращает EINVAL), сопроцессор гоняет звук сам.
Поэтому просто открываем узлы устройства и держим дескрипторы.
"""
import os
import re
import signal
import subprocess
import sys
import time

PLAYBACK = "/dev/snd/pcmC0D6p"     # VoiceMMode1 playback
CAPTURE = "/dev/snd/pcmC0D6c"      # VoiceMMode1 capture
POLL = 1.0                          # с

# состояния вызова, при которых тракт должен быть поднят
ACTIVE_STATES = {"active", "ringing-in", "ringing-out", "dialing", "held"}


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=8).stdout
    except (subprocess.TimeoutExpired, OSError):
        return ""


def call_active():
    modems = re.findall(r"/org/freedesktop/ModemManager1/Modem/(\d+)",
                        sh(["mmcli", "-L"]))
    for m in modems:
        calls = re.findall(r"/org/freedesktop/ModemManager1/Call/(\d+)",
                           sh(["mmcli", "-m", m, "--voice-list-calls"]))
        for call in calls:
            st = re.search(r"state:\s*(\S+)", sh(["mmcli", "-o", call]))
            if st and st.group(1).strip() in ACTIVE_STATES:
                return True
    return False


class VoicePath:
    """Держит голосовой поток открытым, пока идёт разговор."""

    def __init__(self):
        self.fds = []

    @property
    def up(self):
        return bool(self.fds)

    def start(self):
        self.stop()
        try:
            self.fds = [os.open(PLAYBACK, os.O_RDWR),
                        os.open(CAPTURE, os.O_RDONLY)]
            print("разговорный тракт поднят", flush=True)
        except OSError as e:
            print("не удалось открыть голосовой поток: %s" % e, flush=True)
            self.stop()

    def stop(self):
        for fd in self.fds:
            try:
                os.close(fd)
            except OSError:
                pass
        if self.fds:
            print("разговорный тракт опущен", flush=True)
        self.fds = []


def main():
    path = VoicePath()

    def bye(*_):
        path.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, bye)
    signal.signal(signal.SIGINT, bye)

    while True:
        try:
            want = call_active()
            if want and not path.up:
                path.start()
            elif not want and path.up:
                path.stop()
        except Exception as e:                    # служба не должна падать
            print("ошибка опроса: %s" % e, flush=True)
        time.sleep(POLL)


if __name__ == "__main__":
    main()
