# screen.py - Ekran arayüzü: yeşil = kayıtlı parmak izi, kırmızı = kayıtsız
import time
from st7789 import rgb
from utils import ascii_tr

# Durum türü -> arka plan rengi
COLORS = {
    "idle": rgb(0, 40, 110),      # koyu mavi : bekleme / bilgi
    "ok":   rgb(0, 150, 60),      # YEŞİL     : giriş/çıkış izni
    "bad":  rgb(200, 20, 20),     # KIRMIZI   : reddedildi / hata
    "wait": rgb(200, 120, 0),     # turuncu   : kullanıcıdan bir şey bekleniyor
}
WHITE = rgb(255, 255, 255)


class Screen:
    """Ekrana 'durum mesajı' yazar. Hem metin hem de renk ile ne olduğunu gösterir."""

    def __init__(self, panel):
        self.panel = panel
        self._bg = None                 # ekranın şu anki arka plan rengi
        self._band = None               # yazıların kapladığı dikey aralık (üst, alt)
        self._revert_at = None          # bu zamanda bekleme ekranına dönülecek
        self.ip = ""                    # bekleme ekranının altında gösterilecek IP adresi

    def show(self, kind, lines, hold_ms=0):
        """kind: 'idle' | 'ok' | 'bad' | 'wait'
        lines: [(metin, ölçek), ...] satırlar dikeyde ortalanarak yazılır.
        hold_ms > 0 ise o süre sonra otomatik bekleme ekranına dönülür."""
        bg = COLORS[kind]
        p = self.panel
        rows = []                                        # (metin, ölçek) - sığacak şekilde küçültülmüş
        for text, scale in lines:
            text = ascii_tr(text)
            while scale > 1 and len(text) * 8 * scale > p.WIDTH:
                scale -= 1                               # uzun isim -> yazıyı küçült
            rows.append((text, scale))
        total = sum(8 * s for _, s in rows) + 10 * (len(rows) - 1)
        y = (p.HEIGHT - total) // 2

        top = max(0, y - 8)
        bottom = min(p.HEIGHT, y + total + 8)
        if bg != self._bg or self._band is None:
            p.fill(bg)                                   # renk değiştiyse tüm ekranı boya
        else:                                            # aynı renk: sadece eski+yeni yazı bandını sil
            top_all = min(top, self._band[0])
            p.fill_rect(0, top_all, p.WIDTH, max(bottom, self._band[1]) - top_all, bg)
        self._bg = bg
        self._band = (top, bottom)

        for text, scale in rows:
            x = (p.WIDTH - len(text) * 8 * scale) // 2
            p.text(max(x, 0), y, text, WHITE, bg, scale)
            y += 8 * scale + 10

        if hold_ms:
            self._revert_at = time.ticks_add(time.ticks_ms(), hold_ms)
        else:
            self._revert_at = None

    def _idle_lines(self):
        lines = [("PARMAK IZI", 3), ("OKUTUN", 3)]
        if self.ip:
            lines.append((self.ip, 1))
        return lines

    def idle(self, ip=None):
        """Bekleme ekranı: 'PARMAK IZI OKUTUN' (+ varsa IP adresi)."""
        if ip is not None:
            self.ip = ip
        self.show("idle", self._idle_lines())

    def update(self):
        """Ana döngüden çağrılır; sonuç ekranının süresi dolunca bekleme ekranına döner."""
        if self._revert_at is not None and time.ticks_diff(time.ticks_ms(), self._revert_at) >= 0:
            self._revert_at = None
            self.show("idle", self._idle_lines())
