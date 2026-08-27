#!/bin/sh
# Свип фокуса v2: актуатор двигаем в начале окна одиночного захвата
# (CCI жив только во время стрима; stream-skip даёт время линзе доехать)
score() {
python3 - "$1" <<'EOF'
import sys
w, h = 3264, 2448
stride = w * 5 // 4
d = open(sys.argv[1], "rb").read()
tot = 0
for y in range(h//2 - 200, h//2 + 200, 4):
    row = d[y*stride + stride//3 : y*stride + 2*stride//3]
    prev = row[0]
    for i in range(1, len(row), 5):
        b = row[i]
        tot += abs(b - prev)
        prev = b
print(tot)
EOF
}
setpos() {
    i2ctransfer -f -y 9 w2@0x0c 0x02 0x00
    i2ctransfer -f -y 9 w2@0x0c 0x03 $(printf 0x%02x $(($1 >> 8)))
    i2ctransfer -f -y 9 w2@0x0c 0x04 $(printf 0x%02x $(($1 & 255)))
}
BEST=0; BESTPOS=0
for pos in $POSITIONS; do
    rm -f /tmp/f.raw
    v4l2-ctl -d /dev/video0 --stream-mmap --stream-count=1 --stream-skip=25 --stream-to=/tmp/f.raw >/dev/null 2>&1 &
    sleep 0.6
    setpos $pos >/dev/null 2>&1
    wait
    S=$(score /tmp/f.raw)
    echo "pos=$pos резкость=$S"
    if [ "$S" -gt "$BEST" ]; then BEST=$S; BESTPOS=$pos; fi
done
echo "ЛУЧШАЯ: $BESTPOS ($BEST)"
rm -f /tmp/best.raw
v4l2-ctl -d /dev/video0 --stream-mmap --stream-count=1 --stream-skip=25 --stream-to=/tmp/best.raw >/dev/null 2>&1 &
sleep 0.6
setpos $BESTPOS >/dev/null 2>&1
wait
ls -l /tmp/best.raw
