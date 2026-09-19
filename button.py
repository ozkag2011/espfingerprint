# button.py - İçerideki kapı açma butonu
import time
from machine import Pin


class Button:
    """Bir ucu pine, diğer ucu GND'ye bağlı buton. İç pull-up kullanılır (dış direnç gerekmez).
    Titreşimi (debounce) filtreler; basıldığı anda TEK SEFER True döner."""

    def __init__(self, pin_no, debounce_ms=50):
        self.pin = Pin(pin_no, Pin.IN, Pin.PULL_UP)
        self.debounce_ms = debounce_ms
        self._level = 1                                   # 1 = bırakılmış
        self._changed = time.ticks_add(time.ticks_ms(), -debounce_ms)

    def pressed(self):
        """Buton şimdi basıldıysa True. Basılı tutmak tekrar True üretmez."""
        now = time.ticks_ms()
        level = self.pin.value()
        if level != self._level and time.ticks_diff(now, self._changed) >= self.debounce_ms:
            self._level = level
            self._changed = now
            return level == 0                             # 0 = basıldı
        return False
