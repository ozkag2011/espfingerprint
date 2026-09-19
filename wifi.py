# wifi.py - Wi-Fi bağlantısı ve internetten saat eşitleme
import time
import network
import config


class WifiManager:
    """Wi-Fi'ye bağlanır, koparsa yeniden dener, saati NTP ile ayarlar.
    Kapı sistemi Wi-Fi olmadan da çalışır; internet sadece web paneli ve saat içindir."""

    def __init__(self, logger):
        self.log = logger
        self.sta = network.WLAN(network.STA_IF)
        self.sta.active(True)
        network.WLAN(network.AP_IF).active(False)   # Varsayılan açık "MicroPython" ağını kapat (güvenlik)
        self._last_try = time.ticks_ms()
        self._last_ntp = time.ticks_add(time.ticks_ms(), -60000)
        self.time_synced = False

    @property
    def connected(self):
        return self.sta.isconnected()

    @property
    def ip(self):
        return self.sta.ifconfig()[0] if self.sta.isconnected() else ""

    def connect(self, timeout_s=15):
        """Bağlanmayı dener (en fazla timeout_s saniye bekler). Başarılıysa True."""
        if not self.sta.isconnected():
            self.sta.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
            start = time.ticks_ms()
            while not self.sta.isconnected():
                if time.ticks_diff(time.ticks_ms(), start) > timeout_s * 1000:
                    return False
                time.sleep_ms(200)
        self._sync_time()
        return True

    def _sync_time(self):
        """İnternetten saati alır (UTC). Başarısız olursa sessizce devam eder."""
        try:
            import ntptime
            ntptime.settime()
            self.time_synced = True
            self.log.log("SAAT", "Saat internetten ayarlandı")
        except Exception as e:
            self.log.log("SAAT", "Saat ayarlanamadı: {}".format(e))

    def update(self):
        """Ana döngüden çağrılır: kopmuşsa 30 sn'de bir yeniden bağlanır, saati eşitler."""
        now = time.ticks_ms()
        if not self.sta.isconnected():
            if time.ticks_diff(now, self._last_try) > 30000:
                self._last_try = now
                self.sta.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
        elif not self.time_synced and time.ticks_diff(now, self._last_ntp) > 60000:
            self._last_ntp = now
            self._sync_time()
