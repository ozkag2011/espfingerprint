# fingerprint.py - Adafruit (R30x / ZFM-20 uyumlu) parmak izi sensörü sürücüsü
# Harici kütüphane gerekmez; sensörün seri protokolünü doğrudan konuşur.
import gc
import os
import time
from machine import UART
gc.collect()

# ---- Sensör komut kodları ----
_GEN_IMG = 0x01        # parmağın resmini çek
_IMG2TZ = 0x02         # resmi özellik dosyasına (karakter tamponu 1/2) çevir
_SEARCH = 0x04         # tampondaki parmağı hafızada ara
_REG_MODEL = 0x05      # iki tampondan tek şablon üret
_STORE = 0x06          # şablonu hafızaya (numaraya) kaydet
_DELETE = 0x0C         # numaradaki şablonu sil
_READ_PARAMS = 0x0F    # sistem parametreleri (kapasite vb.)
_VERIFY_PWD = 0x13     # sensör şifresi kontrolü (varsayılan 0)
_INDEX_TABLE = 0x1F    # hangi numaralar dolu

# ---- Sensörün onay (confirmation) kodları ----
OK = 0x00
NO_FINGER = 0x02       # sensörde parmak yok
NOT_FOUND = 0x09       # aranan parmak hafızada yok
TIMEOUT = 0xFE         # (bizim kod) sensör cevap vermedi
BAD_REPLY = 0xFF       # (bizim kod) bozuk/yanlış cevap

# ---- identify() sonuçları ----
NONE = 0               # sensörde parmak yok
MATCH = 1              # kayıtlı parmak bulundu
UNKNOWN = 2            # parmak okundu ama kayıtlı değil
POOR = 3               # okuma kötü (tekrar deneyin)
COMM = 4               # sensörle haberleşme hatası

_HEADER = b"\xEF\x01"
_ADDRESS = b"\xFF\xFF\xFF\xFF"


class FingerprintSensor:
    def __init__(self, baud=57600):
        # ESP8266'da sadece UART0 hem TX hem RX yapabilir; USB terminali de onu kullanır.
        # Terminali UART0'dan ayırıyoruz. (Bilgisayara yazı gitmez, REPL kapanır!)
        os.dupterm(None, 1)
        self.uart = UART(0, baud)
        self.capacity = 162               # begin() gerçek değeri okur
        self.last_match_id = -1           # enroll sırasında "zaten kayıtlı" ise kimin olduğu

    # ------------------------------------------------------------------
    #  Düşük seviye: paket gönder / al
    # ------------------------------------------------------------------
    def _read(self, n, timeout_ms):
        """Tam n bayt oku; süre dolarsa None döner."""
        buf = b""
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while len(buf) < n:
            chunk = self.uart.read(n - len(buf))
            if chunk:
                buf += chunk
            elif time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                return None
            else:
                time.sleep_ms(1)
        return buf

    def _transact(self, cmd, params=b"", timeout=600):
        """Komutu yollar, cevabı bekler. Döner: (onay_kodu, ek_veri)."""
        payload = bytes([cmd]) + params
        length = len(payload) + 2                                  # +2 = sağlama toplamı
        body = bytes([0x01, length >> 8, length & 0xFF]) + payload  # 0x01 = komut paketi
        chk = sum(body) & 0xFFFF
        packet = _HEADER + _ADDRESS + body + bytes([chk >> 8, chk & 0xFF])

        while self.uart.any():                                     # eski artık baytları at
            self.uart.read()
        self.uart.write(packet)

        head = self._read(9, timeout)              # başlık(2) adres(4) tür(1) uzunluk(2)
        if head is None:
            return TIMEOUT, b""
        if head[0:2] != _HEADER or head[6] != 0x07:                # 0x07 = cevap paketi
            return BAD_REPLY, b""
        n = (head[7] << 8) | head[8]
        if n < 3:
            return BAD_REPLY, b""
        rest = self._read(n, 500)
        if rest is None:
            return TIMEOUT, b""
        chk = (sum(head[6:9]) + sum(rest[:-2])) & 0xFFFF
        if chk != ((rest[-2] << 8) | rest[-1]):
            return BAD_REPLY, b""
        return rest[0], rest[1:-2]

    # ------------------------------------------------------------------
    #  Temel komutlar
    # ------------------------------------------------------------------
    def begin(self):
        """Sensöre bağlanır. Başarılıysa True."""
        code, _ = self._transact(_VERIFY_PWD, b"\x00\x00\x00\x00", 1000)
        if code != OK:
            return False
        code, data = self._transact(_READ_PARAMS)
        if code == OK and len(data) >= 6:
            self.capacity = (data[4] << 8) | data[5]
        return True

    def capture(self):
        """Parmak resmi çek. OK = parmak var, NO_FINGER = yok."""
        return self._transact(_GEN_IMG)[0]

    def to_template(self, buffer_no):
        """Çekilen resmi tampon 1 veya 2'ye çevir."""
        return self._transact(_IMG2TZ, bytes([buffer_no]), 1000)[0]

    def search(self):
        """Tampon 1'deki parmağı ara. Döner: (kod, numara, skor)."""
        params = bytes([1, 0, 0, self.capacity >> 8, self.capacity & 0xFF])
        code, d = self._transact(_SEARCH, params, 3000)
        if code == OK and len(d) >= 4:
            return code, (d[0] << 8) | d[1], (d[2] << 8) | d[3]
        return code, -1, 0

    def create_model(self):
        return self._transact(_REG_MODEL, b"", 1000)[0]

    def store(self, slot):
        return self._transact(_STORE, bytes([1, slot >> 8, slot & 0xFF]), 1500)[0]

    def delete(self, slot):
        """Numaradaki parmak izini sensör hafızasından siler."""
        return self._transact(_DELETE, bytes([slot >> 8, slot & 0xFF, 0, 1]), 1500)[0]

    def used_slots(self):
        """Hafızada dolu numaraların kümesi. Sensör tabloyu vermezse None."""
        used = set()
        for page in range((self.capacity + 255) // 256):
            code, data = self._transact(_INDEX_TABLE, bytes([page]), 1000)
            if code != OK or len(data) < 32:
                return None
            for i in range(32):
                for bit in range(8):
                    if data[i] & (1 << bit):
                        used.add(page * 256 + i * 8 + bit)
        return used

    def next_free_slot(self, used):
        for i in range(self.capacity):
            if i not in used:
                return i
        return None

    # ------------------------------------------------------------------
    #  Üst seviye: tanıma ve kayıt
    # ------------------------------------------------------------------
    def identify(self):
        """Sensörde parmak varsa kim olduğunu bulur. Döner: (sonuç, numara, skor)."""
        code = self.capture()
        if code in (TIMEOUT, BAD_REPLY):
            return COMM, -1, 0
        if code != OK:                                  # parmak yok (veya anlık okuma hatası)
            return NONE, -1, 0
        if self.to_template(1) != OK:                   # bulanık / az özellik
            return POOR, -1, 0
        code, fid, score = self.search()
        if code == OK:
            return MATCH, fid, score
        if code == NOT_FOUND:
            return UNKNOWN, -1, 0
        return (COMM if code in (TIMEOUT, BAD_REPLY) else POOR), -1, 0

    def enroll_steps(self, slot, wait_ms=15000):
        """Yeni parmak izi kaydı - JENERATÖR. Her adımda bir durum yazısı 'yield' eder,
        beklerken None döner. Böylece kayıt sürerken ana döngü (web sunucusu, iç buton)
        durmadan çalışmaya devam eder.

        Durumlar: place1 -> remove -> place2 -> done
        Hatalar : err_timeout, err_image, err_exists, err_mismatch, err_store
        """
        yield "place1"
        if not (yield from self._wait_finger(True, wait_ms)):
            yield "err_timeout"
            return
        if self.to_template(1) != OK:
            yield "err_image"
            return
        code, fid, _ = self.search()                    # aynı parmak zaten kayıtlı mı?
        if code == OK:
            self.last_match_id = fid
            yield "err_exists"
            return

        yield "remove"
        if not (yield from self._wait_finger(False, wait_ms)):
            yield "err_timeout"
            return

        yield "place2"
        if not (yield from self._wait_finger(True, wait_ms)):
            yield "err_timeout"
            return
        if self.to_template(2) != OK:
            yield "err_image"
            return
        if self.create_model() != OK:                   # iki okuma birbirini tutmadı
            yield "err_mismatch"
            return
        if self.store(slot) != OK:
            yield "err_store"
            return
        yield "done"

    def _wait_finger(self, present, wait_ms):
        """Parmak takılana (present=True) ya da çekilene (False) kadar bekler.
        Süre dolarsa False döner. (enroll_steps içinden 'yield from' ile kullanılır)"""
        start = time.ticks_ms()
        while True:
            code = self.capture()
            if present and code == OK:
                return True
            if (not present) and code == NO_FINGER:
                return True
            if time.ticks_diff(time.ticks_ms(), start) > wait_ms:
                return False
            yield None                                  # ana döngüye dön, sonra tekrar bak
            gc.collect()
