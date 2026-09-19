# st7789.py - GMT130-V1.0 (ST7789, 240x240, CS'siz) ekran sürücüsü
# ESP8266'nın RAM'i az olduğu için tam ekran tampon (framebuffer) YOK;
# şekiller ve yazılar doğrudan ekrana çizilir.
import time
import struct
import framebuf
from machine import Pin


def rgb(r, g, b):
    """0-255 arası r,g,b değerini 16 bit (RGB565) renge çevirir."""
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


class ST7789:
    WIDTH = 240
    HEIGHT = 240

    def __init__(self, spi, dc, res, blk, bgr=False):
        self.spi = spi
        self.dc = Pin(dc, Pin.OUT, value=0)
        self.res = Pin(res, Pin.OUT, value=1)
        self.blk = Pin(blk, Pin.OUT, value=0)          # arka ışık kapalı başlasın
        self._init_panel(0x08 if bgr else 0x00)
        self.blk.value(1)                              # her şey hazır -> ışığı aç

    # ---------------- düşük seviye ----------------
    def _cmd(self, cmd, data=None):
        """Komut gönder (DC=0), varsa arkasından veri (DC=1)."""
        self.dc.value(0)
        self.spi.write(bytes([cmd]))
        if data is not None:
            self.dc.value(1)
            self.spi.write(data)

    def _init_panel(self, madctl):
        # Donanım reset
        self.res.value(1)
        time.sleep_ms(10)
        self.res.value(0)
        time.sleep_ms(20)
        self.res.value(1)
        time.sleep_ms(150)
        self._cmd(0x01)                                # yazılım reset
        time.sleep_ms(150)
        self._cmd(0x11)                                # uyku modundan çık
        time.sleep_ms(120)
        self._cmd(0x3A, b"\x55")                       # 16 bit renk (RGB565)
        self._cmd(0x36, bytes([madctl]))               # yön ve renk sırası
        self._cmd(0x21)                                # renk tersleme AÇIK (IPS panel için şart)
        self._cmd(0x13)                                # normal mod
        time.sleep_ms(10)
        self._cmd(0x29)                                # ekranı aç
        time.sleep_ms(120)

    def _window(self, x0, y0, x1, y1):
        """Sonraki piksel verisinin yazılacağı dikdörtgeni seçer."""
        self._cmd(0x2A, struct.pack(">HH", x0, x1))
        self._cmd(0x2B, struct.pack(">HH", y0, y1))
        self._cmd(0x2C)                                # bellek yazma komutu
        self.dc.value(1)                               # bundan sonrası piksel verisi

    # ---------------- çizim ----------------
    def fill_rect(self, x, y, w, h, color):
        """Dolu dikdörtgen çizer."""
        if w <= 0 or h <= 0:
            return
        self._window(x, y, x + w - 1, y + h - 1)
        row = struct.pack(">H", color) * w             # tek satırlık piksel verisi
        for _ in range(h):
            self.spi.write(row)

    def fill(self, color):
        self.fill_rect(0, 0, self.WIDTH, self.HEIGHT, color)

    def text(self, x, y, s, fg, bg, scale=2):
        """8x8 yazı tipini `scale` kat büyüterek yazar (harf başına 8*scale piksel)."""
        size = 8 * scale
        cell = bytearray(size * size * 2)              # tek harflik piksel tamponu
        line = bytearray(size * 2)                     # büyütülmüş tek satır
        glyph = bytearray(8)                           # harfin 8x8 tek bit/piksel hali
        fb = framebuf.FrameBuffer(glyph, 8, 8, framebuf.MONO_HLSB)
        fg_b = struct.pack(">H", fg)
        bg_b = struct.pack(">H", bg)
        for ch in s:
            if x + size > self.WIDTH:
                break
            fb.fill(0)
            fb.text(ch, 0, 0, 1)
            for row in range(8):
                bits = glyph[row]
                for col in range(8):
                    px = fg_b if bits & (0x80 >> col) else bg_b
                    i = col * scale * 2
                    line[i:i + scale * 2] = px * scale
                for k in range(scale):
                    o = (row * scale + k) * size * 2
                    cell[o:o + size * 2] = line
            self._window(x, y, x + size - 1, y + size - 1)
            self.spi.write(cell)
            x += size
