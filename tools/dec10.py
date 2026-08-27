#!/usr/bin/env python3
# RAW10P -> PNG (GRBG дебайер, простой полулинейный)
import sys, struct
import numpy as np
from PIL import Image
raw, w, h, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
data = np.frombuffer(open(raw,"rb").read(), dtype=np.uint8)
stride = w*5//4
data = data[:stride*h].reshape(h, stride)
b = data.astype(np.uint16)
p = np.zeros((h, w), dtype=np.uint16)
g = b[:, 0:stride].reshape(h, -1, 5)
p[:, 0::4] = (g[:,:,0]<<2) | (g[:,:,4] & 3)
p[:, 1::4] = (g[:,:,1]<<2) | ((g[:,:,4]>>2) & 3)
p[:, 2::4] = (g[:,:,2]<<2) | ((g[:,:,4]>>4) & 3)
p[:, 3::4] = (g[:,:,3]<<2) | ((g[:,:,4]>>6) & 3)
p = np.clip(p.astype(np.int32) - 64, 0, 1023).astype(np.float32)
# GRBG
G1 = p[0::2, 0::2]; R = p[0::2, 1::2]; B = p[1::2, 0::2]; G2 = p[1::2, 1::2]
G = (G1 + G2) / 2
rgb = np.stack([R, G, B], axis=-1)
rgb = rgb / max(rgb.max(), 1)
rgb = np.power(rgb, 0.45) * 255
img = Image.fromarray(rgb.astype(np.uint8))
img = img.rotate(-90, expand=True)
img.save(out)
print("сохранено", out, img.size)
