#!/usr/bin/python3
"""Управление звуком разговора для SM-T385.

Заменяет собой стандартный callaudiod: на этом планшете тот работать
не может. Ему нужен отдельный режим звуковой карты для разговора, а
у нас такой режим невозможен ни в одном виде:

  * если описать его на обычных потоках карты — система звука молча
    отбрасывает весь режим (профиль просто не появляется), и служба
    пишет в журнал "no available output found";
  * если описать на голосовом потоке VoiceMMode1 — режим появляется,
    но выход из него получается пустышкой: этот поток не принимает
    данные, он лишь переключатель для звукового сопроцессора.

Отсюда и симптом: кнопки громкой связи и микрофона в интерфейсе
звонка нажимались, но не залипали и ничего не меняли.

Здесь тот же самый интерфейс сделан напрямую: тракт переключается
регуляторами кодека. Сам разговорный звук поднимает служба
t385-callaudio, которая держит открытым голосовой поток.
"""
import subprocess

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

BUS_NAME = "org.mobian_project.CallAudio"
OBJ_PATH = "/org/mobian_project/CallAudio"
IFACE = "org.mobian_project.CallAudio"

MODE_DEFAULT, MODE_CALL = 0, 1
STATE_OFF, STATE_ON = 0, 1

# Разговорный тракт внутри сопроцессора: вниз через primary MI2S,
# вверх — с микрофонного порта кодека.
# Выключать их нельзя: пока они сброшены, голосовой поток вообще
# не открывается (ошибка «недопустимый аргумент»), и разговорного
# звука не будет ни в одну сторону.
VOICE_ON = [("PRI_MI2S_RX Voice Mixer VoiceMMode1", "1"),
            ("VoiceMMode1 Capture Mixer TERT_MI2S_TX", "1")]

# ЕДИНСТВЕННЫЙ ЖИВОЙ ИЗЛУЧАТЕЛЬ — разговорный динамик у уха.
#
# Проверено вживую 28.08.2026 ровным тоном: при выключенном наушном
# динамике и включённом LINEOUT звука нет вообще, при обратном —
# есть. То есть громкий выход молчит так же, как и нижний динамик
# (у того сгорел буст). Весь звук планшета, включая музыку, выходит
# через щель у экрана.
#
# Поэтому «громкой связи» переключать не на что, и кнопка сделана
# честно полезной: она меняет громкость наушного динамика.
# Шкала RX1 Digital Volume — децибелы от -84, шаг 1 дБ.
EARPIECE_ON = [("RX1 MIX1 INP1", "RX1"), ("RDAC2 MUX", "RX1"), ("EAR_S", "1")]

VOLUME_NORMAL = [("RX1 Digital Volume", "96")]    # +12 дБ, как у музыки
VOLUME_LOUD = [("RX1 Digital Volume", "108")]     # +24 дБ

# Микрофон: основной (AMIC1) через первый АЦП.
MIC_ON = [("DEC1 MUX", "ADC1"), ("CIC1 MUX", "AMIC"), ("ADC1 Volume", "8")]
MIC_MUTE = [("DEC1 MUX", "ZERO")]

INTROSPECT_XML = """<!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN" "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
<node>
  <interface name="org.freedesktop.DBus.Introspectable">
    <method name="Introspect"><arg type="s" direction="out"/></method>
  </interface>
  <interface name="org.freedesktop.DBus.Properties">
    <method name="Get">
      <arg type="s" direction="in"/><arg type="s" direction="in"/>
      <arg type="v" direction="out"/>
    </method>
    <method name="GetAll">
      <arg type="s" direction="in"/><arg type="a{sv}" direction="out"/>
    </method>
    <method name="Set">
      <arg type="s" direction="in"/><arg type="s" direction="in"/>
      <arg type="v" direction="in"/>
    </method>
    <signal name="PropertiesChanged">
      <arg type="s"/><arg type="a{sv}"/><arg type="as"/>
    </signal>
  </interface>
  <interface name="org.mobian_project.CallAudio">
    <method name="SelectMode">
      <arg name="mode" type="u" direction="in"/>
      <arg name="success" type="b" direction="out"/>
    </method>
    <method name="EnableSpeaker">
      <arg name="enable" type="b" direction="in"/>
      <arg name="success" type="b" direction="out"/>
    </method>
    <method name="MuteMic">
      <arg name="mute" type="b" direction="in"/>
      <arg name="success" type="b" direction="out"/>
    </method>
    <property name="AudioMode" type="u" access="read"/>
    <property name="MicState" type="u" access="read"/>
    <property name="SpeakerState" type="u" access="read"/>
  </interface>
</node>
"""


def amixer(pairs):
    for name, value in pairs:
        subprocess.run(["amixer", "-c", "0", "-q", "cset",
                        "name=" + name, value],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class CallAudio(dbus.service.Object):
    def __init__(self, bus):
        super().__init__(bus, OBJ_PATH)
        self.mode = MODE_DEFAULT
        self.mic = STATE_ON
        self.speaker = STATE_OFF

    def _notify(self, prop, value):
        self.PropertiesChanged(IFACE, {prop: dbus.UInt32(value)}, [])

    @dbus.service.method(IFACE, in_signature="u", out_signature="b")
    def SelectMode(self, mode):
        mode = int(mode)
        if mode == MODE_CALL:
            amixer(VOICE_ON)
            amixer(EARPIECE_ON)
            self.MuteMic(False)
            # Начинаем с обычной громкости: кнопка в оболочке при
            # начале разговора тоже не нажата, и состояния сходятся.
            self.EnableSpeaker(False)
        else:
            amixer(EARPIECE_ON + VOLUME_NORMAL + MIC_ON)
        self.mode = mode
        self._notify("AudioMode", mode)
        print("режим: %s" % ("разговор" if mode else "обычный"), flush=True)
        return True

    @dbus.service.method(IFACE, in_signature="b", out_signature="b")
    def EnableSpeaker(self, enable):
        enable = bool(enable)
        amixer(VOLUME_LOUD if enable else VOLUME_NORMAL)
        self.speaker = STATE_ON if enable else STATE_OFF
        self._notify("SpeakerState", self.speaker)
        print("громче: %s" % ("да" if enable else "нет"), flush=True)
        return True

    @dbus.service.method(IFACE, in_signature="b", out_signature="b")
    def MuteMic(self, mute):
        mute = bool(mute)
        amixer(MIC_MUTE if mute else MIC_ON)
        # MicState = 1 означает «микрофон включён»
        self.mic = STATE_OFF if mute else STATE_ON
        self._notify("MicState", self.mic)
        print("микрофон: %s" % ("выключен" if mute else "включён"), flush=True)
        return True

    def _props(self):
        return {"AudioMode": dbus.UInt32(self.mode),
                "MicState": dbus.UInt32(self.mic),
                "SpeakerState": dbus.UInt32(self.speaker)}

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="ss",
                         out_signature="v")
    def Get(self, interface, prop):
        return self._props()[prop]

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="s",
                         out_signature="a{sv}")
    def GetAll(self, interface):
        return self._props()

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="ssv")
    def Set(self, interface, prop, value):
        pass

    @dbus.service.signal(dbus.PROPERTIES_IFACE, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass

    @dbus.service.method(dbus.INTROSPECTABLE_IFACE, in_signature="",
                         out_signature="s")
    def Introspect(self):
        """Своё описание объекта — со свойствами.

        Библиотека, через которую оболочка звонков говорит с нами,
        узнаёт о свойствах только из описания объекта. Стандартное
        описание свойств не перечисляет вовсе, поэтому оболочка
        никогда не узнавала состояние кнопок: они нажимались, команда
        доходила, но кнопка не залипала.
        """
        return INTROSPECT_XML


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    try:
        # Имя занимаем в единственном экземпляре. Иначе каждый вызов
        # плодил новую копию, та перехватывала имя — и состояние
        # кнопок терялось: интерфейс спрашивал уже другую копию.
        name = dbus.service.BusName(BUS_NAME, bus, do_not_queue=True)
    except dbus.exceptions.NameExistsException:
        print("служба уже запущена", flush=True)
        return
    # Ссылку на имя держим до конца работы: без неё сборщик мусора
    # освобождает имя, и на каждый вызов запускается новая копия —
    # состояние кнопок тогда всё время сбрасывается.
    obj = CallAudio(bus)
    obj.bus_name = name
    amixer(VOICE_ON)
    print("управление звуком разговора запущено", flush=True)
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
