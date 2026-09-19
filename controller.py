# controller.py - Ana kontrolcü
import gc
import time
import machine
import config
import utils

gc.collect()

from logger import Logger
from storage import Storage
from relay import DoorLock
from button import Button

gc.collect()


class AccessController:
    """Sistemin beyni. Görevleri:
      - donanım nesnelerini oluşturmak
      - parmak izi / buton olaylarında röleyi açıp ekranı ve kayıtları güncellemek
      - web panelinin isteklerini (durum, kayıt ekle, sil) karşılamak
    """

    def __init__(self):
        self.log = Logger(config.LOG_LINES)
        self.door = DoorLock(config.PIN_RELAY, config.RELAY_ACTIVE_LOW,
                             config.RELAY_OPEN_MS, self.log)
        self.button = Button(config.PIN_BUTTON)
        self.store = Storage(config.MAX_EVENTS)
        
        self.screen = self._make_screen()
        
        from wifi import WifiManager
        self.wifi = WifiManager(self.log)
        gc.collect()

        self.sensor = None
        self.sensor_ok = False
        self._sensor_warned = False
        self.web = None

        self.enroll = None
        self.slots = set()
        self.fails = 0
        self.locked_until = None
        self.wait_release = False
        self._sensor_retry = time.ticks_ms()

    # ------------------------------------------------------------------
    #  Kurulum
    # ------------------------------------------------------------------
    def _make_screen(self):
        """SPI'ı ve ekranı oluşturur (Geç İçe Aktarma)."""
        from st7789 import ST7789
        from screen import Screen
        gc.collect()

        if config.TFT_HW_SPI:
            spi = machine.SPI(1, baudrate=20000000,
                              polarity=config.TFT_SPI_POLARITY, phase=config.TFT_SPI_PHASE)
        else:
            spi = machine.SoftSPI(baudrate=1000000,
                                  polarity=config.TFT_SPI_POLARITY, phase=config.TFT_SPI_PHASE,
                                  sck=machine.Pin(config.PIN_TFT_SCK),
                                  mosi=machine.Pin(config.PIN_TFT_SDA),
                                  miso=machine.Pin(config.PIN_TFT_MISO))
        panel = ST7789(spi, config.PIN_TFT_DC, config.PIN_TFT_RES,
                       config.PIN_TFT_BLK, config.TFT_BGR)
        return Screen(panel)

    def _startup(self):
        self.log.log("SISTEM", "Başlatılıyor")
        self._service_window()
        self.screen.show("idle", [("WIFI", 3), ("BAGLANIYOR", 2)])
        if self.wifi.connect():
            self.log.log("WIFI", "Bağlandı, panel adresi: http://{}".format(self.wifi.ip))
        else:
            self.log.log("WIFI", "Bağlanılamadı; kapı Wi-Fi olmadan çalışır")
        
        from webserver import WebServer
        gc.collect()
        self.web = WebServer(self, self.log)
        
        self.screen.ip = self.wifi.ip
        self._start_sensor()
        if self.sensor is None:
            self.screen.idle()
        self.log.log("SISTEM", "Hazır")

    def _service_window(self):
        if not config.SENSOR_ENABLED:
            return
        self.screen.show("wait", [("SERVIS", 3), ("PENCERESI", 2), ("Ctrl+C", 2)])
        for sec in range(config.SERVICE_WINDOW_S, 0, -1):
            self.log.log("SISTEM", "Durdurmak için Ctrl+C: {} sn".format(sec))
            time.sleep(1)

    def _start_sensor(self):
        if not config.SENSOR_ENABLED:
            self.log.log("SENSOR", "Kapalı (SENSOR_ENABLED=False), yalnızca buton çalışır")
            return
        self.log.console = False
        
        # Açılışta sadece fingerprint'i yüklüyoruz, enroll'u ERTELİYORUZ
        gc.collect()
        import fingerprint as fp
        gc.collect()

        self.sensor = fp.FingerprintSensor(config.FP_BAUD)
        self.enroll = None  # İhtiyaç olduğunda yüklenecek
        self._connect_sensor()

        gc.collect()
        import fingerprint as fp
        from enroll import EnrollManager
        gc.collect()

        self.sensor = fp.FingerprintSensor(config.FP_BAUD)
        self.enroll = EnrollManager(self.sensor, self.store, self.screen, self.log, self.refresh_slots)
        self._connect_sensor()

    def _connect_sensor(self):
        if not self.sensor:
            return
        self.sensor_ok = self.sensor.begin()
        if self.sensor_ok:
            self._sensor_warned = False
            self.refresh_slots()
            self.log.log("SENSOR", "Hazır, kayıtlı parmak izi: {}".format(len(self.slots)))
            self.screen.idle()
        elif not self._sensor_warned:
            self._sensor_warned = True
            self.log.log("SENSOR", "Sensör yanıt vermiyor! Kabloları kontrol edin")
            self.screen.show("bad", [("SENSOR", 3), ("HATASI", 3)])

    def refresh_slots(self):
        if not self.sensor:
            used = set(int(k) for k in self.store.names)
        else:
            used = self.sensor.used_slots()
            if used is None:
                used = set(int(k) for k in self.store.names)
        self.slots = used

    # ------------------------------------------------------------------
    #  Ana döngü
    # ------------------------------------------------------------------
    def run(self):
        self._startup()
        while True:
            self._tick()
            time.sleep_ms(30)

    def _tick(self):
        now = time.ticks_ms()
        self.door.update()
        self.screen.update()
        self.wifi.update()
        if self.web:
            self.web.poll()

        if self.button.pressed():
            self._on_exit_button()
        if self.sensor is None:
            return
            
        # enroll nesnesi varsa ve meşgulse adımla
        if self.enroll and self.enroll.busy:
            self.enroll.step()
        elif not self.sensor_ok:
            if time.ticks_diff(now, self._sensor_retry) > 5000:
                self._sensor_retry = now
                self._connect_sensor()
        else:
            self._scan_finger(now)

    # ------------------------------------------------------------------
    #  Olaylar
    # ------------------------------------------------------------------
    def _scan_finger(self, now):
        if not self.sensor:
            return
            
        import fingerprint as fp

        if self.locked_until is not None:
            if time.ticks_diff(now, self.locked_until) < 0:
                return
            self.locked_until = None
        if self.wait_release:
            code = self.sensor.capture()
            if code == fp.NO_FINGER:
                self.wait_release = False
            elif code in (fp.TIMEOUT, fp.BAD_REPLY):
                self.sensor_ok = False
            return

        result, fid, score = self.sensor.identify()
        if result == fp.NONE:
            return
        self.wait_release = True
        if result == fp.MATCH:
            self._on_match(fid, score)
        elif result == fp.UNKNOWN:
            self._on_unknown()
        elif result == fp.COMM:
            self.sensor_ok = False
            self.wait_release = False
        else:
            self.screen.show("wait", [("TEKRAR", 3), ("DENEYIN", 3)], 1500)

    def _on_match(self, fid, score):
        name = self.store.get_name(fid) or "Kayıt #{}".format(fid)
        self.fails = 0
        self.door.open("{} - parmak izi, skor {}".format(name, score))
        self.store.add_event(utils.now_text(), "in", name)
        self.screen.show("ok", [("HOS GELDIN", 3), (name, 3), ("KAPI ACIK", 2)],
                         config.RESULT_SCREEN_MS)

    def _on_unknown(self):
        self.fails += 1
        self.log.log("ERISIM", "Kayıtsız parmak izi ({}/{})".format(self.fails, config.FP_MAX_FAILS))
        self.store.add_event(utils.now_text(), "deny", "Kayıtsız parmak izi")
        if self.fails >= config.FP_MAX_FAILS:
            self.fails = 0
            self.locked_until = time.ticks_add(time.ticks_ms(), config.FP_LOCKOUT_S * 1000)
            self.log.log("ERISIM", "Çok fazla hatalı deneme, {} sn kilit".format(config.FP_LOCKOUT_S))
            self.screen.show("bad", [("COK FAZLA", 3), ("DENEME", 3), ("BEKLEYIN", 2)],
                             config.RESULT_SCREEN_MS)
        else:
            self.screen.show("bad", [("KAYITLI", 3), ("DEGIL", 3)], config.RESULT_SCREEN_MS)

    def _on_exit_button(self):
        self.door.open("iç buton")
        self.store.add_event(utils.now_text(), "out", "İç buton")
        self.screen.show("ok", [("CIKIS", 3), ("KAPI ACIK", 3)], config.RESULT_SCREEN_MS)

    # ------------------------------------------------------------------
    #  Web panelinin kullandığı fonksiyonlar
    # ------------------------------------------------------------------
    def get_state(self):
        fingers = [[i, self.store.get_name(i) or ""] for i in sorted(self.slots)]
        return {
            "time": utils.now_text(),
            "ip": self.wifi.ip,
            "door": self.door.is_open,
            "sensor": self.sensor_ok,
            "busy": bool(self.enroll and self.enroll.busy),
            "msg": self.enroll.msg if self.enroll else "",
            "fingers": fingers,
            "events": self.store.events,
            "log": self.log.lines,
        }

    def start_enroll(self, name):
        name = name.strip()[:20]
        if not name:
            return False, "İsim boş olamaz"
        if not self.sensor_ok or not self.sensor:
            return False, "Sensör veya kayıt modülü hazır değil"
            
        # Kayıt modülünü SADECE İHTİYAÇ ANINDA yüklüyoruz
        if self.enroll is None:
            gc.collect()
            from enroll import EnrollManager
            gc.collect()
            self.enroll = EnrollManager(self.sensor, self.store, self.screen, self.log, self.refresh_slots)

        if self.enroll.busy:
            return False, "Kayıt zaten sürerken yenisi başlatılamaz"

        self.refresh_slots()
        slot = self.sensor.next_free_slot(self.slots)
        if slot is None:
            return False, "Sensör hafızası dolu"
        self.wait_release = False
        self.enroll.start(name, slot)
        return True, "Kayıt başladı, parmağınızı sensöre koyun"

    def delete_finger(self, fid):
        import fingerprint as fp
        if not self.sensor_ok or not self.sensor:
            return False, "Sensör bağlı değil"
        if self.enroll and self.enroll.busy:
            return False, "Kayıt sürerken silinemez"
        try:
            fid = int(fid)
        except ValueError:
            return False, "Geçersiz numara"
        if self.sensor.delete(fid) != fp.OK:
            return False, "Sensör silemedi"
        name = self.store.get_name(fid) or "#{}".format(fid)
        self.store.remove_name(fid)
        self.refresh_slots()
        self.log.log("KAYIT", "Silindi: {}".format(name))
        return True, "Silindi: {}".format(name)