#!/bin/sh
# Съёмка тыловой камерой (r46+): 3264x2448, стоковая таблица в драйвере
# usage: rearshot.sh [exposure] [gain] (по умолчанию 2400 / 128)
EXP=${1:-2400}
GAIN=${2:-128}
M="media-ctl -d /dev/media0"
$M -r >/dev/null
$M -l "'s5k4h5 8-0037':0->'msm_csiphy0':0[1]" >/dev/null
$M -l "'msm_csiphy0':1->'msm_csid0':0[1]" >/dev/null
$M -l "'msm_csid0':1->'msm_ispif0':0[1]" >/dev/null
$M -l "'msm_ispif0':1->'msm_vfe0_rdi0':0[1]" >/dev/null
for e in "s5k4h5 8-0037" msm_csiphy0 msm_csid0 msm_ispif0 msm_vfe0_rdi0; do
    $M -V "'$e':0[fmt:SGRBG10_1X10/3264x2448]" >/dev/null
done
v4l2-ctl -d /dev/video0 --set-fmt-video=width=3264,height=2448,pixelformat=pgAA >/dev/null
SD=$(for d in /dev/v4l-subdev*; do
    media-ctl -d /dev/media0 -e "s5k4h5 8-0037" >/dev/null 2>&1 && echo $d; done | head -1)
# контролы через субдевайс сенсора
for d in /dev/v4l-subdev*; do
    if v4l2-ctl -d $d --list-ctrls 2>/dev/null | grep -q exposure; then
        NAME=$(v4l2-ctl -d $d --list-ctrls 2>/dev/null | head -1)
        v4l2-ctl -d $d --set-ctrl exposure=$EXP 2>/dev/null && \
        v4l2-ctl -d $d --set-ctrl analogue_gain=$GAIN 2>/dev/null && echo "ctrl via $d"
    fi
done
rm -f /tmp/shot.raw
v4l2-ctl -d /dev/video0 --stream-mmap --stream-count=1 --stream-skip=8 --stream-to=/tmp/shot.raw
ls -l /tmp/shot.raw
