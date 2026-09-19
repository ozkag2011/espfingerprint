# utils.py - Küçük yardımcı fonksiyonlar (saat, URL çözme, ekran için ASCII)
import time
import config

# Ekrandaki 8x8 yazı tipinde Türkçe harfler yok; en yakın ASCII harfe çeviriyoruz.
_TR = {"ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G", "ı": "i", "İ": "I",
       "ö": "o", "Ö": "O", "ş": "s", "Ş": "S", "ü": "u", "Ü": "U"}


def ascii_tr(text):
    """'Şule' -> 'Sule' (ekran yazı tipi sadece ASCII bilir) ve büyük harfe çevirir."""
    return "".join(_TR.get(c, c) for c in text).upper()


def now_text():
    """Yerel saati 'GG.AA.YYYY SS:DD:SN' olarak döndürür. Saat ayarlanmadıysa çizgi döner."""
    t = time.localtime(time.time() + config.TIMEZONE_HOURS * 3600)
    if t[0] < 2024:                       # NTP henüz saati ayarlamamış
        return "--.--.---- --:--:--"
    return "{:02d}.{:02d}.{:04d} {:02d}:{:02d}:{:02d}".format(
        t[2], t[1], t[0], t[3], t[4], t[5])


def url_decode(text):
    """'Ali%20Yılmaz' veya 'Ali+Y%C4%B1lmaz' gibi metni normal metne çevirir (UTF-8)."""
    text = text.replace("+", " ")
    raw = bytearray()
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "%" and i + 2 < len(text):
            try:
                raw.append(int(text[i + 1:i + 3], 16))
                i += 3
                continue
            except ValueError:
                pass
        raw.extend(ch.encode())
        i += 1
    return raw.decode()


def parse_query(query):
    """Query string'i (örn: name=Ali&key=123) sözlüğe dönüştürür."""
    params = {}
    if not query:
        return params
    for part in query.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = v
        else:
            params[part] = ""
    return params
