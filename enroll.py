# enroll.py - Parmak izi kayıt işleminin durum makinesi
import time

class EnrollManager:
    def __init__(self, sensor, store, screen, log, refresh_cb):
        self.sensor = sensor
        self.store = store
        self.screen = screen
        self.log = log
        self.refresh_cb = refresh_cb
        
        self.busy = False
        self.msg = ""
        self._gen = None
        self._name = ""
        self._slot = -1
        self._timeout = 0

    def start(self, name, slot):
        self.busy = True
        self.msg = "Parmağınızı sensöre okutun..."
        self._name = name
        self._slot = slot
        self._gen = self.sensor.enroll_steps(slot)
        self.screen.show("wait", [("KAYIT", 3), ("PARMAK", 2), ("OKUTUN", 2)])
        self.log.log("KAYIT", "'{}' için kayıt başlatıldı (No: {})".format(name, slot))
        self._timeout = time.ticks_add(time.ticks_ms(), 30000)

    def step(self):
        if not self.busy or self._gen is None:
            return

        if time.ticks_diff(time.ticks_ms(), self._timeout) > 0:
            self._fail("Zaman aşımı")
            return

        try:
            state = next(self._gen)
        except StopIteration:
            self.busy = False
            return

        if state is None:
            return 

        if state == "place1":
            pass 
        elif state == "remove":
            self.msg = "Parmağınızı çekin..."
            self.screen.show("wait", [("PARMAGI", 3), ("CEKIN", 3)])
        elif state == "place2":
            self.msg = "Aynı parmağı tekrar okutun..."
            self.screen.show("wait", [("TEKRAR", 3), ("OKUTUN", 3)])
        elif state == "done":
            self._success()
        elif state == "err_timeout":
            self._fail("Sensör zaman aşımı")
        elif state == "err_image":
            self._fail("Parmak iyi okunamadı")
        elif state == "err_exists":
            isim = self.store.get_name(self.sensor.last_match_id) or "#{}".format(self.sensor.last_match_id)
            self._fail("Bu parmak zaten kayıtlı: {}".format(isim))
        elif state == "err_mismatch":
            self._fail("İki okuma eşleşmedi")
        elif state == "err_store":
            self._fail("Sensör hafızasına yazılamadı")

    def _success(self):
        self.store.set_name(self._slot, self._name)
        self.refresh_cb()
        self.msg = "Kayıt başarılı!"
        self.log.log("KAYIT", "'{}' başarıyla kaydedildi".format(self._name))
        self.screen.show("ok", [("KAYIT", 3), ("BASARILI", 3)], 2500)
        self.busy = False

    def _fail(self, reason):
        self.msg = "Hata: {}".format(reason)
        self.log.log("KAYIT", "Kayıt iptal: {}".format(reason))
        self.screen.show("bad", [("KAYIT", 3), ("HATASI", 3)], 2500)
        self.busy = False