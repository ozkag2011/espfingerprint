# relay.py - Röle ile kapı kilidini yöneten sınıf
import time
from machine import Pin


class DoorLock:
    """Röleyi açar, belirli süre sonra kendiliğinden kapatır ve her işlemde mesaj yollar."""

    def __init__(self, pin_no, active_low, open_ms, logger):
        self.active_low = active_low
        self.open_ms = open_ms
        self.log = logger
        self.is_open = False
        self._close_at = None
        # Pini oluşturur oluşturmaz "kapalı" seviyesine getir (açılışta kapı açılmasın)
        self.pin = Pin(pin_no, Pin.OUT, value=1 if active_low else 0)

    def _write(self, energized):
        """Röleyi çektir (True) veya bırak (False). active_low ise seviye tersine çevrilir."""
        val = (not energized) if self.active_low else energized
        self.pin.value(1 if val else 0)

    def open(self, reason=""):
        """RÖLEYİ AÇAR ve bilgisayara/web paneline 'Röle açıldı' mesajı gönderir."""
        self._write(True)
        self.is_open = True
        self._close_at = time.ticks_add(time.ticks_ms(), self.open_ms)
        self.log.log("ROLE", "Röle AÇILDI ({}) - {} ms sonra kapanacak".format(reason, self.open_ms))

    def close(self):
        """Röleyi bırakır (kapı tekrar kilitlenir) ve mesaj yollar."""
        self._write(False)
        self.is_open = False
        self._close_at = None
        self.log.log("ROLE", "Röle KAPANDI (kapı kilitli)")

    def update(self):
        """Ana döngüden sürekli çağrılır; süre dolunca röleyi kapatır."""
        if self.is_open and self._close_at is not None:
            if time.ticks_diff(time.ticks_ms(), self._close_at) >= 0:
                self.close()